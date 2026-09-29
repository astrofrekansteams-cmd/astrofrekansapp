# Firebase kimlik entegrasyonu tasarımı

## B12A Flutter uygulama durumu

Flutter'da `firebase_core` ve `firebase_auth`, `AUTH_MODE=local_jwt|firebase|hybrid`, `FirebaseAuthAdapter`, Firebase ID token sağlayıcısı ve FastAPI `/auth/firebase/session` eşleme akışı eklendi. Yerel JWT giriş/refresh akışı korunur. Firebase token'ı için FastAPI `/auth/refresh` çağrılmaz; SDK gerektiğinde ID token'ı zorla yeniler. Gerçek Firebase proje/platform dosyaları mevcut olmadığı için native Firebase giriş akışı cihazda doğrulanmadı. `firebase_options.dart`, `google-services.json`, `GoogleService-Info.plist` veya sahte proje kimliği üretilmedi.

E-posta/şifre akışı gerçek konfigürasyonla çalışacak şekilde bağlandı. Apple provider çağrısı için adaptör vardır; Firebase Console ve native Apple kurulumu doğrulanmadan kullanılabilir sayılmaz. Google native oturumu, resmi `google_sign_in` ve platform SHA-1/entitlement kurulumu tamamlanmadığından kontrollü `notConfigured` durumundadır. B12B push cihaz temizliği için no-op seam bırakıldı; FCM kurulmuş gibi gösterilmez. Bu bölüm günceldir; aşağıdaki “tasarım anındaki durum” tarihsel kayıttır.

> **Durum: B9'da uygulandı.** Aşağıdaki tasarım kararları geçerli; "henüz
> yapılmadı" diyen cümleler artık geçmişe aittir. Bugünkü durum:
>
> - `users.firebase_uid` (nullable, unique) eklendi — migration `0009_firebase_chat`.
> - `AUTH_MODE=hybrid`: backend hem kendi JWT'sini hem Firebase ID token'ını
>   kabul eder. Mevcut oturumlar bozulmadı.
> - Firebase oturumu için backend JWT **üretilmez**; iki oturum ömrü ve iki
>   iptal hikâyesi yaratmamak için.
> - Aynı e-posta ile otomatik hesap devralma **varsayılan olarak kapalı**
>   (`FIREBASE_AUTO_LINK_VERIFIED_EMAIL=false`); güvenli yol, oturum içinden
>   bağlamaktır.
> - Yetki kaynağı PostgreSQL'dir. Hiçbir iş tablosu Firebase UID'ye foreign key
>   ile bağlanmaz; custom claim'e iş izni konmaz.
> - Gerçek service-account anahtarı repoda değildir; `.env.example` yalnız
>   placeholder içerir ve `.gitignore` service-account dosyalarını kapsar.
>
> Uygulama ayrıntıları: [`firebase_backend.md`](firebase_backend.md) ve
> [`firebase_auth.md`](firebase_auth.md).


## Tasarım anındaki durum (B9 öncesi)

Flutter ve FastAPI şu anda FastAPI'nin kendi access/refresh JWT çiftini kullanır. `ApiAuthRepository` bu sözleşmeye göre hazırlanmıştır. Firebase kimliği henüz devrede değildir; kimlik bilgisi, proje ID'si ve platform config dosyası üretilmedi.

## Hedeflenen akış (B9'da bu şekilde uygulandı)

1. Flutter, `IdentityProvider` adaptörüyle Firebase Authentication oturumu açar.
2. Flutter güncel Firebase ID token'ını FastAPI'ye TLS üzerinden gönderir.
3. FastAPI, Firebase Admin SDK ile imza, issuer, audience, süre ve revocation politikasını doğrular.
4. FastAPI doğrulanmış `uid` değerini yerel PostgreSQL kullanıcısına eşler; eksik kullanıcı için kontrollü kayıt akışı uygular.
5. Uygulama izinleri, abonelik, doğum verisi ve servis yetkisi FastAPI/PostgreSQL tarafında kalır. Firebase token tek başına premium yetki vermez.

Önerilen gelecekteki şema değişikliği: `users.firebase_uid` nullable, unique; mevcut kullanıcı hesaplarını bağlamak için açık bir migrasyon/hesap eşleme prosedürü gerekir. Bu fazda migration yapılmadı. Aynı e-posta otomatik olarak aynı kişi kabul edilmemeli; kimlik bağlama doğrulanmış oturum gerektirir.

Geçiş sırasında mevcut JWT oturumları çalışmaya devam eder. Firebase ID token doğrulaması ayrı bir auth adapter olarak eklenir; hangi akışın ne zaman etkinleşeceği backend B5 sonrasında kararlaştırılır. Refresh token rotasyonu ve `token_reused` işleme mevcut FastAPI akışında korunur.

## Servis sınırları

| Servis | Gelecekteki iş | Yetki kaynağı |
|---|---|---|
| Firebase Auth | Kimlik ve ID token | FastAPI doğrular, yerel kullanıcıya eşler |
| Firestore | Kalıcı sohbet mesajları | FastAPI konuşma üyeliğini ve sipariş/randevu hakkını kurar |
| Realtime Database | Presence, typing, çağrı durumu | FastAPI'nin verdiği ilişki ve rol sınırları |
| Firebase Storage | Mesaj ekleri | Yetkili konuşma üyeliği ve dosya politikası |
| FCM | Push teslimi | FastAPI cihaz kaydı ve bildirim tercihi |

Firestore/RTDB/Storage güvenlik kuralları istemciyi sınırlar; iş yetkisinin tek kaynağı değildir. Konuşma üyeliği, randevu ve ödeme hakkı FastAPI'de doğrulanır. Doğrudan Firebase yazımında kurallar, backend tarafından yönetilen üyelik/ACL verisine bakmalıdır; yetki değiştiğinde bu yansımanın gecikmesi ve iptali tasarımda test edilmelidir.

## Güvenli yapılandırma

- `firebase_options.dart`, `google-services.json` ve `GoogleService-Info.plist` gerçek proje oluşturulana kadar yoktur.
- Firebase Admin service-account anahtarı yalnız backend/CI gizli değişkenlerinde bulunur; Flutter'a gömülmez.
- Firebase mobil config dosyaları tek başına sır sayılmaz, fakat gerçek proje kimliği ve izinler hazır olmadan sahte değer kullanılmaz.
- Uygulama çevrimdışıyken oturum ve yetki değişimlerinin nasıl işlendiği entegrasyon testlerinde doğrulanır.

İlgili kod seam'leri: `lib/core/network/realtime_interfaces.dart`, `lib/features/auth/data/api_auth_repository.dart`.
