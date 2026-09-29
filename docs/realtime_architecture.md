# Realtime, sohbet ve çağrı mimarisi

> **Durum: sohbet, presence, ek dosya ve push B9'da; sesli/görüntülü görüşme
> B10'da uygulandı.** Tasarımdan sapan tek karar: mesaj **yazma** işlemi istemciden
> Firestore'a değil, backend üzerinden yapılır. Yetki kararı sipariş durumuna,
> uzman askıya alınmasına, tamamlanma sonrası ek süreye ve servis
> kataloğuna bağlıdır; güvenlik kuralları bunların hiçbirini göremez. İstemci
> **okumayı** doğrudan Firestore listener'ı ile yapar, yani alma tarafı hâlâ
> anlıktır.
>
> - Sohbet: [`chat_architecture.md`](chat_architecture.md)
> - Presence ve typing: [`presence.md`](presence.md)
> - Ek dosyalar: [`media_attachments.md`](media_attachments.md)
> - Push: [`push_notifications.md`](push_notifications.md)
>
> **Sesli ve görüntülü görüşme B10'da uygulandı** (LiveKit). Aşağıdaki
> `RealTimeCommunicationProvider` sözleşmesi `RealtimeCommunicationProvider`
> olarak hayata geçti. Yetki kararı FastAPI'de, medya LiveKit'te; token kısa
> ömürlü ve en az yetkili (veri kanalı yok, sesli görüşmede kamera yayını
> sunucu tarafından engelli); görüşmeyi ACTIVE yapan yalnızca imzası doğrulanmış
> LiveKit webhook'larıdır. Kayıt yok. Ayrıntı:
> [`call_architecture.md`](call_architecture.md),
> [`call_authorization.md`](call_authorization.md),
> [`call_lifecycle.md`](call_lifecycle.md),
> [`livekit_webhooks.md`](livekit_webhooks.md).


## Veri akışı

| Bileşen | Sorumluluk |
|---|---|
| FastAPI + PostgreSQL | Konuşma oluşturma, üyelik, randevu/sipariş yetkisi, denetim ve referans verisi |
| Firestore | Kalıcı mesajlar ve okunma durumu |
| Realtime Database | Geçici online/typing/call presence |
| Firebase Storage | Yetkili sohbet ekleri |
| FCM | Çevrimdışı kullanıcıya bildirim |
| LiveKit/WebRTC | Ses ve görüntü medyası |

FastAPI önce konuşmayı ve üye yetkisini kaydeder. Firebase güvenlik kuralları doğrudan istemci işlemlerinde üyeliği ayrıca kontrol eder. Firestore kuralları tek başına business authorization kaynağı olmaz. Üyelik iptalinde mesaj/ek erişimi ve FCM hedefleri birlikte güncellenmelidir.

İstemci arayüzleri `IdentityProvider`, `RealtimeChatService`, `PresenceService`, `MediaUploadService`, `PushNotificationService` ve `CallService` olarak tanımlandı. `DisabledRealtimeServices` açıkça devre dışı davranır. Bu fazda herhangi bir sohbet veya çağrı ekranı bağlanmadı.

## LiveKit sınırı

Gelecekteki backend `RealTimeCommunicationProvider` sözleşmesi: `create_room()`, `create_participant_token()`, `end_room()`, `get_room_status()`. Her token verilmeden önce FastAPI, oturum ve randevu/sipariş hakkını doğrular. İstemci `CallService.joinAudio()`, `joinVideo()`, `leave()` çağırır. Room API secret ve imzalama anahtarı Flutter'a hiçbir zaman konmaz. Kısa ömürlü participant token yalnız yetkili kullanıcıya verilir.

## Test edilmesi gereken olaylar

- Üyelik kaldırıldığı anda Firestore, Storage ve LiveKit erişimi iptal olur.
- Ağ kopması presence durumunu süresiz online bırakmaz.
- Mesaj tekrarları idempotent kimlikle tek kayda düşer.
- Eki yükleme başarısızsa mesajda kırık dosya bağlantısı kalmaz.
- Çağrı token'ı başka kullanıcı/room için kullanılamaz.
