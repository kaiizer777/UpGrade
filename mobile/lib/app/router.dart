import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/feed/presentation/screens/feed_screen.dart';
import '../features/onboarding/presentation/screens/onboarding_screen.dart';
import '../features/onboarding/presentation/screens/ready_screen.dart';
import '../features/onboarding/presentation/screens/subjects_screen.dart';
import '../features/roadmap/presentation/screens/roadmap_screen.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: '/',
    routes: [
      GoRoute(
        path: '/',
        name: 'subjects',
        builder: (context, state) => const SubjectsScreen(),
      ),
      GoRoute(
        path: '/subjects/:id/onboarding',
        name: 'onboarding',
        builder: (context, state) {
          final subjectId = state.pathParameters['id']!;
          return OnboardingScreen(
            key: ValueKey('onboarding-$subjectId'),
            subjectId: subjectId,
          );
        },
      ),
      GoRoute(
        path: '/subjects/:id/ready',
        name: 'ready',
        builder: (context, state) {
          final subjectId = state.pathParameters['id']!;
          return ReadyScreen(
            key: ValueKey('ready-$subjectId'),
            subjectId: subjectId,
          );
        },
      ),
      GoRoute(
        path: '/subjects/:id/roadmap',
        name: 'roadmap',
        builder: (context, state) {
          final subjectId = state.pathParameters['id']!;
          return RoadmapScreen(
            key: ValueKey('roadmap-$subjectId'),
            subjectId: subjectId,
          );
        },
      ),
      GoRoute(
        path: '/subjects/:id/feed',
        name: 'feed',
        builder: (context, state) {
          final subjectId = state.pathParameters['id']!;
          return FeedScreen(
            key: ValueKey('feed-$subjectId'),
            subjectId: subjectId,
          );
        },
      ),
    ],
  );
});
