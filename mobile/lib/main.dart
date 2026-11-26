import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

void main() {
  runApp(const SarchahanApp());
}

class SarchahanApp extends StatefulWidget {
  const SarchahanApp({super.key});

  @override
  State<SarchahanApp> createState() => _SarchahanAppState();
}

class _SarchahanAppState extends State<SarchahanApp> {
  Locale locale = const Locale('fa');

  void changeLanguage() {
    setState(() {
      locale = locale.languageCode == 'fa'
          ? const Locale('en')
          : const Locale('fa');
    });
  }

  @override
  Widget build(BuildContext context) {
    final isFa = locale.languageCode == 'fa';

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      locale: locale,
      supportedLocales: const [
        Locale('fa'),
        Locale('en'),
      ],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF176B55),
        ),
        useMaterial3: true,
      ),
      home: Directionality(
        textDirection: isFa ? TextDirection.rtl : TextDirection.ltr,
        child: LoginPage(
          isFa: isFa,
          onLanguageChange: changeLanguage,
        ),
      ),
    );
  }
}

class LoginPage extends StatelessWidget {
  final bool isFa;
  final VoidCallback onLanguageChange;

  const LoginPage({
    super.key,
    required this.isFa,
    required this.onLanguageChange,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F7F5),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                const Icon(
                  Icons.school_rounded,
                  size: 85,
                  color: Color(0xFF176B55),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Sarchahan School',
                  style: TextStyle(
                    fontSize: 27,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF176B55),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  isFa
                      ? 'سامانه هوشمند مدیریت مدرسه'
                      : 'Smart School Management System',
                  style: const TextStyle(fontSize: 15),
                ),
                const SizedBox(height: 35),
                Card(
                  elevation: 2,
                  child: Padding(
                    padding: const EdgeInsets.all(22),
                    child: Column(
                      children: [
                        Text(
                          isFa ? 'ورود به سامانه' : 'Sign In',
                          style: const TextStyle(
                            fontSize: 21,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(height: 25),
                        TextField(
                          decoration: InputDecoration(
                            labelText: isFa ? 'نام کاربری' : 'Username',
                            prefixIcon: const Icon(Icons.person_outline),
                            border: const OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          obscureText: true,
                          decoration: InputDecoration(
                            labelText: isFa ? 'رمز عبور' : 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            border: const OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          width: double.infinity,
                          height: 50,
                          child: FilledButton(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text(
                                    isFa
                                        ? 'اتصال به سرور در مرحله بعد فعال می‌شود'
                                        : 'Server connection will be added next',
                                  ),
                                ),
                              );
                            },
                            child: Text(
                              isFa ? 'ورود' : 'Login',
                              style: const TextStyle(fontSize: 17),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                TextButton.icon(
                  onPressed: onLanguageChange,
                  icon: const Icon(Icons.language),
                  label: Text(
                    isFa ? 'English' : 'فارسی',
                  ),
                ),
                const SizedBox(height: 20),
                Text(
                  'Sarchahan School © 2026',
                  style: TextStyle(color: Colors.grey.shade600),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}