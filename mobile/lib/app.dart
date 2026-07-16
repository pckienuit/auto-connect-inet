import 'package:flutter/material.dart';

import 'src/platform/auto_login_platform.dart';
import 'src/screens/dashboard_screen.dart';

class InetAutoLoginApp extends StatelessWidget {
  const InetAutoLoginApp({super.key, this.platform});
  final AutoLoginApi? platform;

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'INET Auto Login',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff006a60)),
          useMaterial3: true,
        ),
        home: DashboardScreen(platform: platform ?? AutoLoginPlatform()),
      );
}
