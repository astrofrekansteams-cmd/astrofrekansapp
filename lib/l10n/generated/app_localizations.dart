import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_tr.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('tr'),
  ];

  /// No description provided for @appName.
  ///
  /// In tr, this message translates to:
  /// **'Astrofrekans'**
  String get appName;

  /// No description provided for @appTagline.
  ///
  /// In tr, this message translates to:
  /// **'Kendi Gökyüzünü Keşfet'**
  String get appTagline;

  /// No description provided for @brandMotto.
  ///
  /// In tr, this message translates to:
  /// **'DAHA BİLİNÇLİ  •  DAHA DENGELİ  •  DAHA SEN'**
  String get brandMotto;

  /// No description provided for @universeSpeaks.
  ///
  /// In tr, this message translates to:
  /// **'Evren her zaman konuşur, sen sadece dinle.'**
  String get universeSpeaks;

  /// No description provided for @commonContinue.
  ///
  /// In tr, this message translates to:
  /// **'Devam Et'**
  String get commonContinue;

  /// No description provided for @commonBack.
  ///
  /// In tr, this message translates to:
  /// **'Geri'**
  String get commonBack;

  /// No description provided for @commonSkip.
  ///
  /// In tr, this message translates to:
  /// **'Geç'**
  String get commonSkip;

  /// No description provided for @commonSeeAll.
  ///
  /// In tr, this message translates to:
  /// **'Tümünü Gör'**
  String get commonSeeAll;

  /// No description provided for @commonMoreInfo.
  ///
  /// In tr, this message translates to:
  /// **'Daha fazla bilgi'**
  String get commonMoreInfo;

  /// No description provided for @commonRetry.
  ///
  /// In tr, this message translates to:
  /// **'Tekrar Dene'**
  String get commonRetry;

  /// No description provided for @commonClose.
  ///
  /// In tr, this message translates to:
  /// **'Kapat'**
  String get commonClose;

  /// No description provided for @commonCancel.
  ///
  /// In tr, this message translates to:
  /// **'Vazgeç'**
  String get commonCancel;

  /// No description provided for @commonSave.
  ///
  /// In tr, this message translates to:
  /// **'Kaydet'**
  String get commonSave;

  /// No description provided for @commonSoon.
  ///
  /// In tr, this message translates to:
  /// **'Yakında'**
  String get commonSoon;

  /// No description provided for @commonToday.
  ///
  /// In tr, this message translates to:
  /// **'Bugün'**
  String get commonToday;

  /// No description provided for @commonOptional.
  ///
  /// In tr, this message translates to:
  /// **'isteğe bağlı'**
  String get commonOptional;

  /// No description provided for @commonSelect.
  ///
  /// In tr, this message translates to:
  /// **'Seç'**
  String get commonSelect;

  /// No description provided for @commonDemoMode.
  ///
  /// In tr, this message translates to:
  /// **'DEMO'**
  String get commonDemoMode;

  /// No description provided for @commonDemoNotice.
  ///
  /// In tr, this message translates to:
  /// **'Sunucu bağlı değil. Veriler örnek (mock) servisten geliyor.'**
  String get commonDemoNotice;

  /// No description provided for @errorGeneric.
  ///
  /// In tr, this message translates to:
  /// **'Bir şeyler ters gitti.'**
  String get errorGeneric;

  /// No description provided for @errorNetwork.
  ///
  /// In tr, this message translates to:
  /// **'İnternet bağlantısı yok.'**
  String get errorNetwork;

  /// No description provided for @errorTimeout.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzüne ulaşılamadı, zaman aşımı.'**
  String get errorTimeout;

  /// No description provided for @errorUnauthorized.
  ///
  /// In tr, this message translates to:
  /// **'Oturumun sona erdi, tekrar giriş yap.'**
  String get errorUnauthorized;

  /// No description provided for @errorServer.
  ///
  /// In tr, this message translates to:
  /// **'Sunucu şu anda yanıt vermiyor.'**
  String get errorServer;

  /// No description provided for @onboardingSlide1Title.
  ///
  /// In tr, this message translates to:
  /// **'Kendi Gökyüzünü Keşfet'**
  String get onboardingSlide1Title;

  /// No description provided for @onboardingSlide1Body.
  ///
  /// In tr, this message translates to:
  /// **'Doğum haritan, sadece sana ait bir gökyüzü haritasıdır. Astrofrekans onu senin için okur.'**
  String get onboardingSlide1Body;

  /// No description provided for @onboardingSlide2Title.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzü Seninle Konuşuyor'**
  String get onboardingSlide2Title;

  /// No description provided for @onboardingSlide2Body.
  ///
  /// In tr, this message translates to:
  /// **'Günlük transitler, Ay fazları ve kişisel frekansın; hepsi tek bir akışta.'**
  String get onboardingSlide2Body;

  /// No description provided for @onboardingSlide3Title.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI'**
  String get onboardingSlide3Title;

  /// No description provided for @onboardingSlide3Body.
  ///
  /// In tr, this message translates to:
  /// **'Doğum haritanla konuş. Sorularını gökyüzünün rehberliğinde yanıtlasın.'**
  String get onboardingSlide3Body;

  /// No description provided for @onboardingSlide4Title.
  ///
  /// In tr, this message translates to:
  /// **'Tarot • Rune • Katina'**
  String get onboardingSlide4Title;

  /// No description provided for @onboardingSlide4Body.
  ///
  /// In tr, this message translates to:
  /// **'İçsel rehberlik için kartlar, taşlar ve semboller yanında.'**
  String get onboardingSlide4Body;

  /// No description provided for @onboardingStart.
  ///
  /// In tr, this message translates to:
  /// **'Hadi Başlayalım'**
  String get onboardingStart;

  /// No description provided for @onboardingHaveAccount.
  ///
  /// In tr, this message translates to:
  /// **'Zaten hesabım var'**
  String get onboardingHaveAccount;

  /// No description provided for @pillarAstrology.
  ///
  /// In tr, this message translates to:
  /// **'ASTROLOJİ'**
  String get pillarAstrology;

  /// No description provided for @pillarAstrologySub.
  ///
  /// In tr, this message translates to:
  /// **'Kendini Tanı'**
  String get pillarAstrologySub;

  /// No description provided for @pillarTarot.
  ///
  /// In tr, this message translates to:
  /// **'TAROT'**
  String get pillarTarot;

  /// No description provided for @pillarTarotSub.
  ///
  /// In tr, this message translates to:
  /// **'Yolunu Gör'**
  String get pillarTarotSub;

  /// No description provided for @pillarRune.
  ///
  /// In tr, this message translates to:
  /// **'RUNE'**
  String get pillarRune;

  /// No description provided for @pillarRuneSub.
  ///
  /// In tr, this message translates to:
  /// **'Gücünü Hisset'**
  String get pillarRuneSub;

  /// No description provided for @pillarKatina.
  ///
  /// In tr, this message translates to:
  /// **'KATİNA'**
  String get pillarKatina;

  /// No description provided for @pillarKatinaSub.
  ///
  /// In tr, this message translates to:
  /// **'İç Sesini Dinle'**
  String get pillarKatinaSub;

  /// No description provided for @authLoginTitle.
  ///
  /// In tr, this message translates to:
  /// **'Tekrar Hoş Geldin'**
  String get authLoginTitle;

  /// No description provided for @authLoginSubtitle.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzü seni bekliyordu.'**
  String get authLoginSubtitle;

  /// No description provided for @authRegisterTitle.
  ///
  /// In tr, this message translates to:
  /// **'Kendi Gökyüzünü Aç'**
  String get authRegisterTitle;

  /// No description provided for @authRegisterSubtitle.
  ///
  /// In tr, this message translates to:
  /// **'Doğum bilgilerin haritanın temelidir.'**
  String get authRegisterSubtitle;

  /// No description provided for @authEmail.
  ///
  /// In tr, this message translates to:
  /// **'E-posta'**
  String get authEmail;

  /// No description provided for @authPassword.
  ///
  /// In tr, this message translates to:
  /// **'Şifre'**
  String get authPassword;

  /// No description provided for @authPasswordConfirm.
  ///
  /// In tr, this message translates to:
  /// **'Şifre tekrar'**
  String get authPasswordConfirm;

  /// No description provided for @authName.
  ///
  /// In tr, this message translates to:
  /// **'Ad Soyad'**
  String get authName;

  /// No description provided for @authBirthDate.
  ///
  /// In tr, this message translates to:
  /// **'Doğum tarihi'**
  String get authBirthDate;

  /// No description provided for @authBirthTime.
  ///
  /// In tr, this message translates to:
  /// **'Doğum saati'**
  String get authBirthTime;

  /// No description provided for @authBirthTimeUnknown.
  ///
  /// In tr, this message translates to:
  /// **'Doğum saatimi bilmiyorum'**
  String get authBirthTimeUnknown;

  /// No description provided for @authBirthPlace.
  ///
  /// In tr, this message translates to:
  /// **'Doğum yeri'**
  String get authBirthPlace;

  /// No description provided for @authBirthPlaceHint.
  ///
  /// In tr, this message translates to:
  /// **'Şehir, ülke'**
  String get authBirthPlaceHint;

  /// No description provided for @authLogin.
  ///
  /// In tr, this message translates to:
  /// **'Giriş Yap'**
  String get authLogin;

  /// No description provided for @authRegister.
  ///
  /// In tr, this message translates to:
  /// **'Hesap Oluştur'**
  String get authRegister;

  /// No description provided for @authForgotPassword.
  ///
  /// In tr, this message translates to:
  /// **'Şifremi unuttum'**
  String get authForgotPassword;

  /// No description provided for @authForgotTitle.
  ///
  /// In tr, this message translates to:
  /// **'Şifreni sıfırla'**
  String get authForgotTitle;

  /// No description provided for @authForgotSubtitle.
  ///
  /// In tr, this message translates to:
  /// **'Hesabının e-posta adresini yaz. Hesap uygunsa sana bir sıfırlama bağlantısı göndereceğiz.'**
  String get authForgotSubtitle;

  /// No description provided for @authForgotSubmit.
  ///
  /// In tr, this message translates to:
  /// **'Bağlantı gönder'**
  String get authForgotSubmit;

  /// No description provided for @authForgotRequested.
  ///
  /// In tr, this message translates to:
  /// **'Hesap uygunsa sıfırlama bağlantısı gönderildi. Bağlantı 30 dakika geçerlidir ve bir kez kullanılabilir.'**
  String get authForgotRequested;

  /// No description provided for @authForgotCheckSpam.
  ///
  /// In tr, this message translates to:
  /// **'E-postayı göremiyorsan gereksiz klasörünü kontrol et.'**
  String get authForgotCheckSpam;

  /// No description provided for @authForgotUnavailable.
  ///
  /// In tr, this message translates to:
  /// **'Şifre sıfırlama e-postası şu anda gönderilemiyor. Lütfen daha sonra tekrar dene.'**
  String get authForgotUnavailable;

  /// No description provided for @authBackToLogin.
  ///
  /// In tr, this message translates to:
  /// **'Girişe dön'**
  String get authBackToLogin;

  /// No description provided for @authResetTitle.
  ///
  /// In tr, this message translates to:
  /// **'Yeni şifre belirle'**
  String get authResetTitle;

  /// No description provided for @authResetChecking.
  ///
  /// In tr, this message translates to:
  /// **'Bağlantı kontrol ediliyor…'**
  String get authResetChecking;

  /// No description provided for @authResetNewPassword.
  ///
  /// In tr, this message translates to:
  /// **'Yeni şifre'**
  String get authResetNewPassword;

  /// No description provided for @authResetSubmit.
  ///
  /// In tr, this message translates to:
  /// **'Şifreyi güncelle'**
  String get authResetSubmit;

  /// No description provided for @authResetDone.
  ///
  /// In tr, this message translates to:
  /// **'Şifren güncellendi. Yeni şifrenle giriş yapabilirsin.'**
  String get authResetDone;

  /// No description provided for @authResetExpired.
  ///
  /// In tr, this message translates to:
  /// **'Bu bağlantının süresi dolmuş. Yeni bir bağlantı iste.'**
  String get authResetExpired;

  /// No description provided for @authResetUsed.
  ///
  /// In tr, this message translates to:
  /// **'Bu bağlantı daha önce kullanılmış veya yerine yenisi istenmiş.'**
  String get authResetUsed;

  /// No description provided for @authResetInvalid.
  ///
  /// In tr, this message translates to:
  /// **'Bu sıfırlama bağlantısı geçersiz.'**
  String get authResetInvalid;

  /// No description provided for @authResetRequestNew.
  ///
  /// In tr, this message translates to:
  /// **'Yeni bağlantı iste'**
  String get authResetRequestNew;

  /// No description provided for @authNoAccount.
  ///
  /// In tr, this message translates to:
  /// **'Hesabın yok mu?'**
  String get authNoAccount;

  /// No description provided for @authHasAccount.
  ///
  /// In tr, this message translates to:
  /// **'Zaten hesabın var mı?'**
  String get authHasAccount;

  /// No description provided for @authAccountSection.
  ///
  /// In tr, this message translates to:
  /// **'Hesap bilgileri'**
  String get authAccountSection;

  /// No description provided for @authBirthSection.
  ///
  /// In tr, this message translates to:
  /// **'Doğum bilgileri'**
  String get authBirthSection;

  /// No description provided for @authBirthDataWhy.
  ///
  /// In tr, this message translates to:
  /// **'Doğum saatin yükselen burcunu ve ev sistemini belirler. Bilmiyorsan sonra ekleyebilirsin.'**
  String get authBirthDataWhy;

  /// No description provided for @authContinueWithGoogle.
  ///
  /// In tr, this message translates to:
  /// **'Google ile devam et'**
  String get authContinueWithGoogle;

  /// No description provided for @authContinueWithApple.
  ///
  /// In tr, this message translates to:
  /// **'Apple ile devam et'**
  String get authContinueWithApple;

  /// No description provided for @authSocialSoon.
  ///
  /// In tr, this message translates to:
  /// **'Sosyal giriş yakında etkinleşecek.'**
  String get authSocialSoon;

  /// No description provided for @authOr.
  ///
  /// In tr, this message translates to:
  /// **'veya'**
  String get authOr;

  /// No description provided for @authSignOut.
  ///
  /// In tr, this message translates to:
  /// **'Çıkış Yap'**
  String get authSignOut;

  /// No description provided for @validationRequired.
  ///
  /// In tr, this message translates to:
  /// **'Bu alan zorunlu.'**
  String get validationRequired;

  /// No description provided for @validationEmail.
  ///
  /// In tr, this message translates to:
  /// **'Geçerli bir e-posta gir.'**
  String get validationEmail;

  /// No description provided for @validationPasswordShort.
  ///
  /// In tr, this message translates to:
  /// **'Şifre en az 8 karakter olmalı.'**
  String get validationPasswordShort;

  /// No description provided for @validationPasswordMatch.
  ///
  /// In tr, this message translates to:
  /// **'Şifreler eşleşmiyor.'**
  String get validationPasswordMatch;

  /// No description provided for @validationNameShort.
  ///
  /// In tr, this message translates to:
  /// **'Adın en az 2 karakter olmalı.'**
  String get validationNameShort;

  /// No description provided for @validationBirthDate.
  ///
  /// In tr, this message translates to:
  /// **'Doğum tarihini seç.'**
  String get validationBirthDate;

  /// No description provided for @validationBirthPlace.
  ///
  /// In tr, this message translates to:
  /// **'Doğum yerini yaz.'**
  String get validationBirthPlace;

  /// No description provided for @authInvalidCredentials.
  ///
  /// In tr, this message translates to:
  /// **'E-posta veya şifre hatalı.'**
  String get authInvalidCredentials;

  /// No description provided for @authEmailInUse.
  ///
  /// In tr, this message translates to:
  /// **'Bu e-posta zaten kayıtlı.'**
  String get authEmailInUse;

  /// No description provided for @navToday.
  ///
  /// In tr, this message translates to:
  /// **'Bugün'**
  String get navToday;

  /// No description provided for @navSky.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzü'**
  String get navSky;

  /// No description provided for @navAstroAi.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI'**
  String get navAstroAi;

  /// No description provided for @navExplore.
  ///
  /// In tr, this message translates to:
  /// **'Keşfet'**
  String get navExplore;

  /// No description provided for @navProfile.
  ///
  /// In tr, this message translates to:
  /// **'Profil'**
  String get navProfile;

  /// No description provided for @homeGreeting.
  ///
  /// In tr, this message translates to:
  /// **'Merhaba'**
  String get homeGreeting;

  /// No description provided for @homeUniverseTalking.
  ///
  /// In tr, this message translates to:
  /// **'Evren seninle konuşuyor.'**
  String get homeUniverseTalking;

  /// No description provided for @homeNotifications.
  ///
  /// In tr, this message translates to:
  /// **'Bildirimler'**
  String get homeNotifications;

  /// No description provided for @homeLanguage.
  ///
  /// In tr, this message translates to:
  /// **'Dil'**
  String get homeLanguage;

  /// No description provided for @homeFrequencyTitle.
  ///
  /// In tr, this message translates to:
  /// **'Bugünün Frekansı'**
  String get homeFrequencyTitle;

  /// No description provided for @homeFrequencyOf100.
  ///
  /// In tr, this message translates to:
  /// **'/100'**
  String get homeFrequencyOf100;

  /// No description provided for @homeFrequencyHigh.
  ///
  /// In tr, this message translates to:
  /// **'Yüksek Frekans'**
  String get homeFrequencyHigh;

  /// No description provided for @homeFrequencyBalanced.
  ///
  /// In tr, this message translates to:
  /// **'Dengeli Frekans'**
  String get homeFrequencyBalanced;

  /// No description provided for @homeFrequencyCalm.
  ///
  /// In tr, this message translates to:
  /// **'Sakin Frekans'**
  String get homeFrequencyCalm;

  /// No description provided for @homeFrequencyEveryDay.
  ///
  /// In tr, this message translates to:
  /// **'Her gün yeni bir sen.'**
  String get homeFrequencyEveryDay;

  /// No description provided for @homeTodayAffecting.
  ///
  /// In tr, this message translates to:
  /// **'Bugün seni etkileyen'**
  String get homeTodayAffecting;

  /// No description provided for @homeAskAstroAi.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI\'\'ya Sor'**
  String get homeAskAstroAi;

  /// No description provided for @homeAskAstroAiSub.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzünün rehberliğinde, merak ettiğin her şeyi sor.'**
  String get homeAskAstroAiSub;

  /// No description provided for @homeAskHint.
  ///
  /// In tr, this message translates to:
  /// **'Bugün benim için ne söylüyor?'**
  String get homeAskHint;

  /// No description provided for @homeSend.
  ///
  /// In tr, this message translates to:
  /// **'Gönder'**
  String get homeSend;

  /// No description provided for @homeCosmicCalendar.
  ///
  /// In tr, this message translates to:
  /// **'Kozmik Takvim'**
  String get homeCosmicCalendar;

  /// No description provided for @homeInnerGuidance.
  ///
  /// In tr, this message translates to:
  /// **'İçsel Rehberlik'**
  String get homeInnerGuidance;

  /// No description provided for @homeInnerGuidanceSub.
  ///
  /// In tr, this message translates to:
  /// **'Kendi yolculuğunu keşfet.'**
  String get homeInnerGuidanceSub;

  /// No description provided for @homeScoreSemantics.
  ///
  /// In tr, this message translates to:
  /// **'Bugünün frekansı {score} / 100'**
  String homeScoreSemantics(int score);

  /// No description provided for @metricGeneralEnergy.
  ///
  /// In tr, this message translates to:
  /// **'Genel Enerji'**
  String get metricGeneralEnergy;

  /// No description provided for @metricLove.
  ///
  /// In tr, this message translates to:
  /// **'Aşk'**
  String get metricLove;

  /// No description provided for @metricCareer.
  ///
  /// In tr, this message translates to:
  /// **'Kariyer'**
  String get metricCareer;

  /// No description provided for @metricMoney.
  ///
  /// In tr, this message translates to:
  /// **'Para'**
  String get metricMoney;

  /// No description provided for @metricMood.
  ///
  /// In tr, this message translates to:
  /// **'Ruh Hali'**
  String get metricMood;

  /// No description provided for @metricHealth.
  ///
  /// In tr, this message translates to:
  /// **'Sağlık'**
  String get metricHealth;

  /// No description provided for @metricLuck.
  ///
  /// In tr, this message translates to:
  /// **'Şans'**
  String get metricLuck;

  /// No description provided for @astroAiTitle.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI'**
  String get astroAiTitle;

  /// No description provided for @astroAiKicker.
  ///
  /// In tr, this message translates to:
  /// **'SOR  •  KEŞFET  •  FARK ET'**
  String get astroAiKicker;

  /// No description provided for @astroAiHeroLine1.
  ///
  /// In tr, this message translates to:
  /// **'Doğum haritanı okur.'**
  String get astroAiHeroLine1;

  /// No description provided for @astroAiHeroLine2.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzünü senin için yorumlar.'**
  String get astroAiHeroLine2;

  /// No description provided for @astroAiHeroNote.
  ///
  /// In tr, this message translates to:
  /// **'Doğum haritanı ve güncel gökyüzü hareketlerini analiz ederek sorularını senin için yanıtlar.'**
  String get astroAiHeroNote;

  /// No description provided for @astroAiFeaturePersonal.
  ///
  /// In tr, this message translates to:
  /// **'KİŞİSEL\nYORUM'**
  String get astroAiFeaturePersonal;

  /// No description provided for @astroAiFeatureTransits.
  ///
  /// In tr, this message translates to:
  /// **'GÜNCEL\nTRANSİTLER'**
  String get astroAiFeatureTransits;

  /// No description provided for @astroAiFeatureAwareness.
  ///
  /// In tr, this message translates to:
  /// **'DAHA DERİN\nFARKINDALIK'**
  String get astroAiFeatureAwareness;

  /// No description provided for @astroAiInputHint.
  ///
  /// In tr, this message translates to:
  /// **'Bir şey sor...'**
  String get astroAiInputHint;

  /// No description provided for @astroAiInfluencesTitle.
  ///
  /// In tr, this message translates to:
  /// **'Bu yorumu oluşturan etkiler'**
  String get astroAiInfluencesTitle;

  /// No description provided for @astroAiThinking.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzü okunuyor...'**
  String get astroAiThinking;

  /// No description provided for @astroAiTyping.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI yazıyor...'**
  String get astroAiTyping;

  /// No description provided for @astroAiError.
  ///
  /// In tr, this message translates to:
  /// **'Astro AI şu an yanıt veremedi.'**
  String get astroAiError;

  /// No description provided for @astroAiAttachmentSoon.
  ///
  /// In tr, this message translates to:
  /// **'Dosya ekleme yakında.'**
  String get astroAiAttachmentSoon;

  /// No description provided for @astroAiVoiceSoon.
  ///
  /// In tr, this message translates to:
  /// **'Sesli soru yakında.'**
  String get astroAiVoiceSoon;

  /// No description provided for @astroAiEmptyTitle.
  ///
  /// In tr, this message translates to:
  /// **'İlk sorunu sor'**
  String get astroAiEmptyTitle;

  /// No description provided for @astroAiEmptyBody.
  ///
  /// In tr, this message translates to:
  /// **'Doğum haritan hazır. Merak ettiğin konuyu yaz ya da aşağıdaki önerilerden birini seç.'**
  String get astroAiEmptyBody;

  /// No description provided for @astroAiPromptLove.
  ///
  /// In tr, this message translates to:
  /// **'Aşk hayatım nasıl?'**
  String get astroAiPromptLove;

  /// No description provided for @astroAiPromptCareer.
  ///
  /// In tr, this message translates to:
  /// **'Kariyerimde ne görünüyor?'**
  String get astroAiPromptCareer;

  /// No description provided for @astroAiPromptEnergy.
  ///
  /// In tr, this message translates to:
  /// **'Bugünün enerjisi ne?'**
  String get astroAiPromptEnergy;

  /// No description provided for @astroAiPromptTransits.
  ///
  /// In tr, this message translates to:
  /// **'Şu an üzerimde hangi transitler etkili?'**
  String get astroAiPromptTransits;

  /// No description provided for @influenceSupportive.
  ///
  /// In tr, this message translates to:
  /// **'Destekleyici Etki'**
  String get influenceSupportive;

  /// No description provided for @influenceChallenging.
  ///
  /// In tr, this message translates to:
  /// **'Zorlayıcı Etki'**
  String get influenceChallenging;

  /// No description provided for @influenceEmotional.
  ///
  /// In tr, this message translates to:
  /// **'Duygusal Odak'**
  String get influenceEmotional;

  /// No description provided for @influenceLesson.
  ///
  /// In tr, this message translates to:
  /// **'Ders ve Sınırlar'**
  String get influenceLesson;

  /// No description provided for @influenceNeutral.
  ///
  /// In tr, this message translates to:
  /// **'Etkin Gökyüzü'**
  String get influenceNeutral;

  /// No description provided for @skyTitle.
  ///
  /// In tr, this message translates to:
  /// **'Gökyüzü'**
  String get skyTitle;

  /// No description provided for @skySubtitle.
  ///
  /// In tr, this message translates to:
  /// **'Kendi haritan ve güncel gökyüzü.'**
  String get skySubtitle;

  /// No description provided for @skyNatalChart.
  ///
  /// In tr, this message translates to:
  /// **'Doğum Haritam'**
  String get skyNatalChart;

  /// No description provided for @skyNatalChartSub.
  ///
  /// In tr, this message translates to:
  /// **'Gezegenler, evler, açılar'**
  String get skyNatalChartSub;

  /// No description provided for @skyTransits.
  ///
  /// In tr, this message translates to:
  /// **'Transitler'**
  String get skyTransits;

  /// No description provided for @skyTransitsSub.
  ///
  /// In tr, this message translates to:
  /// **'Bugün ve yaklaşan etkiler'**
  String get skyTransitsSub;

  /// No description provided for @skyCosmicCalendar.
  ///
  /// In tr, this message translates to:
  /// **'Kozmik Takvim'**
  String get skyCosmicCalendar;

  /// No description provided for @skyCosmicCalendarSub.
  ///
  /// In tr, this message translates to:
  /// **'Ay fazları, retrolar, tutulmalar'**
  String get skyCosmicCalendarSub;

  /// No description provided for @skyCompatibility.
  ///
  /// In tr, this message translates to:
  /// **'Uyum Analizi'**
  String get skyCompatibility;

  /// No description provided for @skyCompatibilitySub.
  ///
  /// In tr, this message translates to:
  /// **'Sinastri ve composite'**
  String get skyCompatibilitySub;

  /// No description provided for @exploreTitle.
  ///
  /// In tr, this message translates to:
  /// **'Keşfet'**
  String get exploreTitle;

  /// No description provided for @exploreSubtitle.
  ///
  /// In tr, this message translates to:
  /// **'İçsel rehberlik ve daha fazlası.'**
  String get exploreSubtitle;

  /// No description provided for @exploreTarot.
  ///
  /// In tr, this message translates to:
  /// **'Tarot'**
  String get exploreTarot;

  /// No description provided for @exploreTarotSub.
  ///
  /// In tr, this message translates to:
  /// **'78 kart, klasik açılımlar'**
  String get exploreTarotSub;

  /// No description provided for @exploreRune.
  ///
  /// In tr, this message translates to:
  /// **'Rune'**
  String get exploreRune;

  /// No description provided for @exploreRuneSub.
  ///
  /// In tr, this message translates to:
  /// **'Elder Futhark, 24 rune'**
  String get exploreRuneSub;

  /// No description provided for @exploreKatina.
  ///
  /// In tr, this message translates to:
  /// **'Katina'**
  String get exploreKatina;

  /// No description provided for @exploreKatinaSub.
  ///
  /// In tr, this message translates to:
  /// **'65 kart, sezgisel okuma'**
  String get exploreKatinaSub;

  /// No description provided for @exploreConsultants.
  ///
  /// In tr, this message translates to:
  /// **'Canlı Danışmanlık'**
  String get exploreConsultants;

  /// No description provided for @exploreConsultantsSub.
  ///
  /// In tr, this message translates to:
  /// **'Uzmanlarla birebir görüşme'**
  String get exploreConsultantsSub;

  /// No description provided for @explorePremium.
  ///
  /// In tr, this message translates to:
  /// **'Premium'**
  String get explorePremium;

  /// No description provided for @explorePremiumSub.
  ///
  /// In tr, this message translates to:
  /// **'Sınırsız içgörü'**
  String get explorePremiumSub;

  /// No description provided for @profileTitle.
  ///
  /// In tr, this message translates to:
  /// **'Profil'**
  String get profileTitle;

  /// No description provided for @profilePremiumBadge.
  ///
  /// In tr, this message translates to:
  /// **'PREMIUM'**
  String get profilePremiumBadge;

  /// No description provided for @profileFreePlan.
  ///
  /// In tr, this message translates to:
  /// **'Ücretsiz plan'**
  String get profileFreePlan;

  /// No description provided for @profileAccount.
  ///
  /// In tr, this message translates to:
  /// **'Hesap Bilgileri'**
  String get profileAccount;

  /// No description provided for @profileBirthData.
  ///
  /// In tr, this message translates to:
  /// **'Doğum Bilgileri'**
  String get profileBirthData;

  /// No description provided for @profileSavedPeople.
  ///
  /// In tr, this message translates to:
  /// **'Kaydedilen Kişiler'**
  String get profileSavedPeople;

  /// No description provided for @profileNotifications.
  ///
  /// In tr, this message translates to:
  /// **'Bildirimler'**
  String get profileNotifications;

  /// No description provided for @profilePrivacy.
  ///
  /// In tr, this message translates to:
  /// **'Gizlilik ve Güvenlik'**
  String get profilePrivacy;

  /// No description provided for @profileLanguage.
  ///
  /// In tr, this message translates to:
  /// **'Dil'**
  String get profileLanguage;

  /// No description provided for @profileSignOutConfirm.
  ///
  /// In tr, this message translates to:
  /// **'Çıkış yapmak istediğine emin misin?'**
  String get profileSignOutConfirm;

  /// No description provided for @comingSoonTitle.
  ///
  /// In tr, this message translates to:
  /// **'Yakında'**
  String get comingSoonTitle;

  /// No description provided for @comingSoonBody.
  ///
  /// In tr, this message translates to:
  /// **'Bu bölüm bir sonraki geliştirme fazında açılacak.'**
  String get comingSoonBody;

  /// No description provided for @languageTurkish.
  ///
  /// In tr, this message translates to:
  /// **'Türkçe'**
  String get languageTurkish;

  /// No description provided for @languageEnglish.
  ///
  /// In tr, this message translates to:
  /// **'İngilizce'**
  String get languageEnglish;

  /// No description provided for @moonPhaseNew.
  ///
  /// In tr, this message translates to:
  /// **'Yeni Ay'**
  String get moonPhaseNew;

  /// No description provided for @moonPhaseWaxingCrescent.
  ///
  /// In tr, this message translates to:
  /// **'Hilal (Büyüyen)'**
  String get moonPhaseWaxingCrescent;

  /// No description provided for @moonPhaseFirstQuarter.
  ///
  /// In tr, this message translates to:
  /// **'İlk Dördün'**
  String get moonPhaseFirstQuarter;

  /// No description provided for @moonPhaseWaxingGibbous.
  ///
  /// In tr, this message translates to:
  /// **'Şişkin Ay (Büyüyen)'**
  String get moonPhaseWaxingGibbous;

  /// No description provided for @moonPhaseFull.
  ///
  /// In tr, this message translates to:
  /// **'Dolunay'**
  String get moonPhaseFull;

  /// No description provided for @moonPhaseWaningGibbous.
  ///
  /// In tr, this message translates to:
  /// **'Şişkin Ay (Küçülen)'**
  String get moonPhaseWaningGibbous;

  /// No description provided for @moonPhaseLastQuarter.
  ///
  /// In tr, this message translates to:
  /// **'Son Dördün'**
  String get moonPhaseLastQuarter;

  /// No description provided for @moonPhaseWaningCrescent.
  ///
  /// In tr, this message translates to:
  /// **'Hilal (Küçülen)'**
  String get moonPhaseWaningCrescent;

  /// No description provided for @moonInSign.
  ///
  /// In tr, this message translates to:
  /// **'Ay {sign} burcunda'**
  String moonInSign(String sign);

  /// No description provided for @signAries.
  ///
  /// In tr, this message translates to:
  /// **'Koç'**
  String get signAries;

  /// No description provided for @signTaurus.
  ///
  /// In tr, this message translates to:
  /// **'Boğa'**
  String get signTaurus;

  /// No description provided for @signGemini.
  ///
  /// In tr, this message translates to:
  /// **'İkizler'**
  String get signGemini;

  /// No description provided for @signCancer.
  ///
  /// In tr, this message translates to:
  /// **'Yengeç'**
  String get signCancer;

  /// No description provided for @signLeo.
  ///
  /// In tr, this message translates to:
  /// **'Aslan'**
  String get signLeo;

  /// No description provided for @signVirgo.
  ///
  /// In tr, this message translates to:
  /// **'Başak'**
  String get signVirgo;

  /// No description provided for @signLibra.
  ///
  /// In tr, this message translates to:
  /// **'Terazi'**
  String get signLibra;

  /// No description provided for @signScorpio.
  ///
  /// In tr, this message translates to:
  /// **'Akrep'**
  String get signScorpio;

  /// No description provided for @signSagittarius.
  ///
  /// In tr, this message translates to:
  /// **'Yay'**
  String get signSagittarius;

  /// No description provided for @signCapricorn.
  ///
  /// In tr, this message translates to:
  /// **'Oğlak'**
  String get signCapricorn;

  /// No description provided for @signAquarius.
  ///
  /// In tr, this message translates to:
  /// **'Kova'**
  String get signAquarius;

  /// No description provided for @signPisces.
  ///
  /// In tr, this message translates to:
  /// **'Balık'**
  String get signPisces;

  /// No description provided for @planetSun.
  ///
  /// In tr, this message translates to:
  /// **'Güneş'**
  String get planetSun;

  /// No description provided for @planetMoon.
  ///
  /// In tr, this message translates to:
  /// **'Ay'**
  String get planetMoon;

  /// No description provided for @planetMercury.
  ///
  /// In tr, this message translates to:
  /// **'Merkür'**
  String get planetMercury;

  /// No description provided for @planetVenus.
  ///
  /// In tr, this message translates to:
  /// **'Venüs'**
  String get planetVenus;

  /// No description provided for @planetMars.
  ///
  /// In tr, this message translates to:
  /// **'Mars'**
  String get planetMars;

  /// No description provided for @planetJupiter.
  ///
  /// In tr, this message translates to:
  /// **'Jüpiter'**
  String get planetJupiter;

  /// No description provided for @planetSaturn.
  ///
  /// In tr, this message translates to:
  /// **'Satürn'**
  String get planetSaturn;

  /// No description provided for @planetUranus.
  ///
  /// In tr, this message translates to:
  /// **'Uranüs'**
  String get planetUranus;

  /// No description provided for @planetNeptune.
  ///
  /// In tr, this message translates to:
  /// **'Neptün'**
  String get planetNeptune;

  /// No description provided for @planetPluto.
  ///
  /// In tr, this message translates to:
  /// **'Plüton'**
  String get planetPluto;

  /// No description provided for @planetNorthNode.
  ///
  /// In tr, this message translates to:
  /// **'Kuzey Ay Düğümü'**
  String get planetNorthNode;

  /// No description provided for @planetSouthNode.
  ///
  /// In tr, this message translates to:
  /// **'Güney Ay Düğümü'**
  String get planetSouthNode;

  /// No description provided for @aspectConjunction.
  ///
  /// In tr, this message translates to:
  /// **'kavuşum'**
  String get aspectConjunction;

  /// No description provided for @aspectSextile.
  ///
  /// In tr, this message translates to:
  /// **'sekstil'**
  String get aspectSextile;

  /// No description provided for @aspectSquare.
  ///
  /// In tr, this message translates to:
  /// **'kare'**
  String get aspectSquare;

  /// No description provided for @aspectTrine.
  ///
  /// In tr, this message translates to:
  /// **'üçgen'**
  String get aspectTrine;

  /// No description provided for @aspectOpposition.
  ///
  /// In tr, this message translates to:
  /// **'karşıt'**
  String get aspectOpposition;

  /// No description provided for @houseOrdinal.
  ///
  /// In tr, this message translates to:
  /// **'{house}. Ev'**
  String houseOrdinal(int house);

  /// No description provided for @retrogradeShort.
  ///
  /// In tr, this message translates to:
  /// **'Rx'**
  String get retrogradeShort;

  /// No description provided for @retrogradeOf.
  ///
  /// In tr, this message translates to:
  /// **'{planet} Rx'**
  String retrogradeOf(String planet);

  /// No description provided for @transitIntoHouse.
  ///
  /// In tr, this message translates to:
  /// **'{planet} → {house}. Ev'**
  String transitIntoHouse(String planet, int house);

  /// No description provided for @transitAspect.
  ///
  /// In tr, this message translates to:
  /// **'{transiting} {aspect} {natal}'**
  String transitAspect(String transiting, String aspect, String natal);

  /// No description provided for @emptyNoData.
  ///
  /// In tr, this message translates to:
  /// **'Henüz veri yok'**
  String get emptyNoData;

  /// No description provided for @emptyNoBirthData.
  ///
  /// In tr, this message translates to:
  /// **'Doğum bilgin eksik'**
  String get emptyNoBirthData;

  /// No description provided for @emptyOffline.
  ///
  /// In tr, this message translates to:
  /// **'Bağlantı yok'**
  String get emptyOffline;

  /// No description provided for @emptyNoResults.
  ///
  /// In tr, this message translates to:
  /// **'Sonuç bulunamadı'**
  String get emptyNoResults;

  /// No description provided for @emptyPremiumLocked.
  ///
  /// In tr, this message translates to:
  /// **'Premium içerik'**
  String get emptyPremiumLocked;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'tr'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'tr':
      return AppLocalizationsTr();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
