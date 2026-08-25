import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../data/api_client.dart';
import '../../domain/models.dart';
import '../providers.dart';

/// `/subjects/:id/ready` — confirmation screen with the captured profile.
///
/// Phase 3 placeholder: the actual roadmap lands here in Phase 4.
class ReadyScreen extends ConsumerWidget {
  const ReadyScreen({super.key, required this.subjectId});

  final String subjectId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(onboardingStateProvider(subjectId));
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(title: const Text('All set')),
      body: Center(
        child: state.when(
          loading: () => const CircularProgressIndicator(),
          error: (error, _) => Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(Icons.cloud_off_outlined,
                    size: 56, color: colorScheme.error),
                const SizedBox(height: 12),
                Text(
                  error is ApiException ? error.message : error.toString(),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton.tonalIcon(
                  key: const Key('ready-retry'),
                  onPressed: () =>
                      ref.invalidate(onboardingStateProvider(subjectId)),
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              ],
            ),
          ),
          data: (state) => SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                CircleAvatar(
                  key: const Key('ready-avatar'),
                  radius: 36,
                  backgroundColor: colorScheme.primaryContainer,
                  child:
                      Icon(Icons.check_rounded, size: 44, color: colorScheme.onPrimaryContainer),
                ),
                const SizedBox(height: 16),
                Text(
                  "You're all set!",
                  textAlign: TextAlign.center,
                  style: theme.textTheme.headlineSmall
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 6),
                Text(
                  'UpGrade understood what you need. Here\'s your learning profile:',
                  textAlign: TextAlign.center,
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: colorScheme.outline),
                ),
                const SizedBox(height: 20),
                _ProfileCard(profile: state.profile),
                const SizedBox(height: 24),
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 16, vertical: 14),
                  decoration: BoxDecoration(
                    color: colorScheme.secondaryContainer.withValues(alpha: 0.5),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Row(
                    children: [
                      Icon(Icons.map_outlined,
                          color: colorScheme.onSecondaryContainer),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Your personalized roadmap will appear here next.',
                          style: theme.textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSecondaryContainer),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                FilledButton.icon(
                  key: const Key('view-roadmap'),
                  onPressed: () => context.go('/subjects/$subjectId/roadmap'),
                  icon: const Icon(Icons.map_outlined),
                  label: const Text('View your roadmap'),
                ),
                const SizedBox(height: 8),
                FilledButton.tonalIcon(
                  key: const Key('back-to-subjects'),
                  onPressed: () => context.go('/'),
                  icon: const Icon(Icons.list_alt_rounded),
                  label: const Text('Back to subjects'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ProfileCard extends StatelessWidget {
  const _ProfileCard({required this.profile});

  final OnboardingProfile? profile;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final profile = this.profile;

    return Card(
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(color: colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: profile == null
            ? Padding(
                padding: const EdgeInsets.symmetric(vertical: 16),
                child: Text(
                  'No profile details were returned for this subject.',
                  style: theme.textTheme.bodyMedium
                      ?.copyWith(color: colorScheme.outline),
                ),
              )
            : Column(
                key: const Key('profile-card'),
                children: [
                  _Row(label: 'Goal', value: profile.goal),
                  _Divider(),
                  _Row(label: 'Current level', value: profile.currentLevel),
                  _Divider(),
                  _Row(label: 'Background', value: profile.background),
                  _Divider(),
                  _Row(label: 'Motivation', value: profile.motivation),
                  _Divider(),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 110,
                          child: Text('Pace',
                              style: theme.textTheme.labelLarge?.copyWith(
                                  color: colorScheme.outline)),
                        ),
                        Expanded(
                          child: Wrap(
                            spacing: 8,
                            runSpacing: 4,
                            children: [
                              if (profile.pacePreference != null)
                                Chip(
                                  key: const Key('pace-chip'),
                                  avatar: Icon(
                                    switch (profile.pacePreference!) {
                                      PacePreference.chill =>
                                        Icons.spa_outlined,
                                      PacePreference.steady =>
                                        Icons.directions_walk_outlined,
                                      PacePreference.intense =>
                                        Icons.bolt_outlined,
                                    },
                                    size: 16,
                                  ),
                                  label: Text(
                                      profile.pacePreference!.name),
                                  visualDensity: VisualDensity.compact,
                                )
                              else
                                Text('—',
                                    style: theme.textTheme.bodyMedium),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
      ),
    );
  }
}

class _Divider extends StatelessWidget {
  @override
  Widget build(BuildContext context) =>
      Divider(height: 1, color: Theme.of(context).colorScheme.outlineVariant);
}

class _Row extends StatelessWidget {
  const _Row({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label,
                style:
                    theme.textTheme.labelLarge?.copyWith(color: colorScheme.outline)),
          ),
          Expanded(
            child: Text(value,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(fontWeight: FontWeight.w500)),
          ),
        ],
      ),
    );
  }
}
