plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.compose)
    id("com.fajarnuha.gradle-graph")
}

android {
    namespace = "com.fajarnuha"
    compileSdk = 36

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    defaultConfig {
        applicationId = "com.fajarnuha"
        minSdk = 24
        targetSdk = 36
    }
    buildFeatures { compose = true }
}

dependencies {
    implementation(project(":feature"))
    implementation(project(":shared"))
    implementation(libs.activity.compose)
    implementation(libs.compose.material3)
    testImplementation(libs.junit)
}

kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
