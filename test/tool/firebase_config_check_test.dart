// The Firebase config check that guards release builds: right project,
// right package / bundle id, an app id from that project, both platforms
// from the same project. Sample files, not real keys.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';

import '../../tool/firebase_config_check.dart';

String _json({
  String project = 'astrofrekans-prod',
  String number = '111222333444',
  String package = 'com.astrofrekans.astrofrekans',
  String? appId,
}) => jsonEncode({
  'project_info': {'project_id': project, 'project_number': number},
  'client': [
    {
      'client_info': {
        'mobilesdk_app_id': appId ?? '1:$number:android:abc123',
        'android_client_info': {'package_name': package},
      },
      'api_key': [
        {'current_key': 'not-a-real-key'},
      ],
    },
  ],
});

String _plist({
  String project = 'astrofrekans-prod',
  String sender = '111222333444',
  String bundle = 'com.astrofrekans.astrofrekans',
  String? appId,
}) =>
    '''
<plist version="1.0"><dict>
  <key>API_KEY</key><string>not-a-real-key</string>
  <key>GCM_SENDER_ID</key><string>$sender</string>
  <key>BUNDLE_ID</key><string>$bundle</string>
  <key>PROJECT_ID</key><string>$project</string>
  <key>GOOGLE_APP_ID</key><string>${appId ?? '1:$sender:ios:def456'}</string>
</dict></plist>''';

void main() {
  test('production files for this app pass and match each other', () {
    final android = checkGoogleServicesJson(_json(), production: true);
    final ios = checkGoogleServiceInfoPlist(_plist(), production: true);
    expect(android.problems, isEmpty);
    expect(ios.problems, isEmpty);
    expect(crossCheck(android.facts!, ios.facts!), isEmpty);
    expect(android.facts!.appIdentifier, 'com.astrofrekans.astrofrekans');
    expect(android.facts.toString(), isNot(contains('not-a-real-key')));
  });

  test('staging is fine for staging and refused for production', () {
    final staging = _json(project: 'astrofrekans-staging');
    expect(checkGoogleServicesJson(staging, production: false).ok, isTrue);
    expect(checkGoogleServicesJson(staging, production: true).ok, isFalse);
    final plist = _plist(project: 'astrofrekans-staging');
    expect(checkGoogleServiceInfoPlist(plist, production: true).ok, isFalse);
  });

  test('another package or bundle id is refused', () {
    expect(
      checkGoogleServicesJson(
        _json(package: 'com.example.other'),
        production: false,
      ).problems.single,
      contains('exactly one Android app'),
    );
    expect(
      checkGoogleServiceInfoPlist(
        _plist(bundle: 'com.example.other'),
        production: false,
      ).problems.single,
      contains('BUNDLE_ID'),
    );
  });

  test('an app id from another project is refused', () {
    expect(
      checkGoogleServicesJson(
        _json(appId: '1:999:android:abc'),
        production: false,
      ).ok,
      isFalse,
    );
    expect(
      checkGoogleServiceInfoPlist(
        _plist(appId: '1:999:ios:abc'),
        production: false,
      ).ok,
      isFalse,
    );
  });

  test('Android and iOS from different projects are refused', () {
    final android = checkGoogleServicesJson(_json(), production: true).facts!;
    final ios = checkGoogleServiceInfoPlist(
      _plist(project: 'astrofrekans-other', sender: '555'),
      production: true,
    ).facts!;
    expect(crossCheck(android, ios), hasLength(1));
  });
}
