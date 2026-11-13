# Android dependency graph sample

- Kotlin and Compose. The app package and application ID are `com.fajarnuha`.
- `:app` shows the relationships among `:app`, `:feature`, and `:shared` on one screen.
- From the repository root, run `./gradlew -p samples/android :app:assembleDebug :app:testDebugUnitTest`.
- Run `./gradlew -p samples/android :app:exportDependencyGraph -PdependencyGraphConfiguration=debugRuntimeClasspath` to generate the report.
- Use `android run` to launch the debug APK and `android layout` to check the screen.
