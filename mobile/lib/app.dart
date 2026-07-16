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
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff2757d8),
        primary: const Color(0xff244fca),
        secondary: const Color(0xffff5c45),
        surface: Colors.white,
      ),
      scaffoldBackgroundColor: const Color(0xfff4f6fb),
      useMaterial3: true,
      cardTheme: const CardThemeData(
        color: Colors.white,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(24)),
          side: BorderSide(color: Color(0xffe8eaf2)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(0, 50),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          side: const BorderSide(color: Color(0xffdfe3ef)),
          textStyle: const TextStyle(fontWeight: FontWeight.w700),
        ),
      ),
    ),
    home: DashboardScreen(platform: platform ?? AutoLoginPlatform()),
  );
}
