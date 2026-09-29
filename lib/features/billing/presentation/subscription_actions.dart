import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/localization/b12_copy.dart';

final billingLinkLauncherProvider = Provider<Future<bool> Function(Uri)>(
  (ref) =>
      (uri) => launchUrl(uri, mode: LaunchMode.externalApplication),
);

Uri subscriptionManagementUri({required bool apple}) => Uri.parse(
  apple
      ? 'https://apps.apple.com/account/subscriptions'
      : 'https://play.google.com/store/account/subscriptions',
);

Future<void> openBillingLink(
  BuildContext context,
  WidgetRef ref,
  Uri uri,
) async {
  try {
    if (await ref.read(billingLinkLauncherProvider)(uri)) return;
  } on Object {
    // The same recovery message covers a missing browser and launch failure.
  }
  if (context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(b12(context, 'subscription_link_failed'))),
    );
  }
}

/// A subscription may have been bought on a different device/platform.
/// Let the owner choose the purchasing store rather than infer it from this OS.
Future<void> manageSubscription(BuildContext context, WidgetRef ref) async {
  final apple = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (context) => SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(b12(context, 'subscription_choose_store')),
            ListTile(
              key: const ValueKey('manage-apple'),
              title: const Text('App Store'),
              trailing: const Icon(Icons.open_in_new),
              onTap: () => Navigator.pop(context, true),
            ),
            ListTile(
              key: const ValueKey('manage-google'),
              title: const Text('Google Play'),
              trailing: const Icon(Icons.open_in_new),
              onTap: () => Navigator.pop(context, false),
            ),
          ],
        ),
      ),
    ),
  );
  if (apple != null && context.mounted) {
    await openBillingLink(
      context,
      ref,
      subscriptionManagementUri(apple: apple),
    );
  }
}

/// Supplied at build time; never invent or ship placeholder legal pages.
class BillingLegalLinks {
  const BillingLegalLinks({
    this.terms = '',
    this.privacy = '',
    this.support =
        'https://astrofrekansteams-cmd.github.io/astrofrekansapp/support.html',
    this.deletion =
        'https://astrofrekansteams-cmd.github.io/astrofrekansapp/delete-account.html',
  });
  final String terms, privacy, support, deletion;
  static Uri? validUrl(String value) {
    final uri = Uri.tryParse(value);
    return uri != null && uri.scheme == 'https' && uri.host.isNotEmpty
        ? uri
        : null;
  }
}

final billingLegalLinksProvider = Provider<BillingLegalLinks>(
  (ref) => const BillingLegalLinks(
    terms: String.fromEnvironment('TERMS_URL'),
    privacy: String.fromEnvironment(
      'PRIVACY_URL',
      defaultValue: 'https://astrofrekansteams-cmd.github.io/astrofrekansapp/',
    ),
  ),
);

class SubscriptionLegalLinks extends ConsumerWidget {
  const SubscriptionLegalLinks({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final links = ref.watch(billingLegalLinksProvider);
    return Wrap(
      alignment: WrapAlignment.center,
      children: [
        for (final entry in [
          ('subscription_terms', links.terms),
          ('subscription_privacy', links.privacy),
          ('subscription_support', links.support),
          ('account_deletion_help', links.deletion),
        ])
          if (BillingLegalLinks.validUrl(entry.$2) case final Uri uri)
            TextButton(
              onPressed: () => openBillingLink(context, ref, uri),
              child: Text(b12(context, entry.$1)),
            ),
      ],
    );
  }
}
