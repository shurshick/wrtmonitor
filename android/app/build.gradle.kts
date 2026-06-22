plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "ru.wrtmonitor.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "ru.wrtmonitor.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 24
        versionName = "0.1.1-rc8"
    }

    signingConfigs {
        getByName("debug") {
            storeFile = rootProject.file("android/debug.keystore")
            storePassword = "wrtmonitor"
            keyAlias = "wrtmonitor-debug"
            keyPassword = "wrtmonitor"
        }
    }

    buildFeatures {
        compose = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.15"
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    testImplementation("junit:junit:4.13.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
}

