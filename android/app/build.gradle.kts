plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.google.devtools.ksp")
}

val siteProofVersionCode = providers.gradleProperty("SITEPROOF_VERSION_CODE")
    .orElse("5")
    .map(String::toInt)
val siteProofVersionName = providers.gradleProperty("SITEPROOF_VERSION_NAME")
    .orElse("0.5.0")
val siteProofUpdateManifestUrl = providers.gradleProperty("SITEPROOF_UPDATE_MANIFEST_URL")
    .orElse("https://github.com/sahid-code404/SiteProof/releases/download/inspector-latest/siteproof-update.json")

android {
    namespace = "com.siteproof.app"
    compileSdk = 36

    signingConfigs {
        create("devDebug") {
            // Development-only signing identity. The debug package uses an applicationId
            // suffix so this key can never sign or update the production SiteProof package.
            storeFile = rootProject.file("dev-signing/siteproof-dev.keystore")
            storePassword = "siteproof-dev"
            keyAlias = "siteproof-dev"
            keyPassword = "siteproof-dev"
        }
    }

    defaultConfig {
        applicationId = "com.siteproof.app"
        minSdk = 26
        targetSdk = 35
        versionCode = siteProofVersionCode.get()
        versionName = siteProofVersionName.get()
        buildConfigField(
            "String",
            "SITEPROOF_UPDATE_MANIFEST_URL",
            "\"${siteProofUpdateManifestUrl.get()}\"",
        )
    }

    buildTypes {
        getByName("debug") {
            // One-time bootstrap installs as com.siteproof.app.dev. All subsequent dev APKs
            // share the stable development certificate and can update in place.
            applicationIdSuffix = ".dev"
            signingConfig = signingConfigs.getByName("devDebug")
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.activity:activity-compose:1.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-moshi:2.11.0")
    implementation("com.squareup.moshi:moshi-kotlin:1.15.2")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")

    implementation("androidx.camera:camera-camera2:1.6.1")
    implementation("androidx.camera:camera-lifecycle:1.6.1")
    implementation("androidx.camera:camera-video:1.6.1")
    implementation("androidx.camera:camera-view:1.6.1")
    implementation("com.google.android.gms:play-services-location:21.4.0")
    implementation("androidx.work:work-runtime-ktx:2.11.2")
    implementation("androidx.room:room-runtime:2.8.4")
    implementation("androidx.room:room-ktx:2.8.4")
    ksp("androidx.room:room-compiler:2.8.4")

    debugImplementation("androidx.compose.ui:ui-tooling")

    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.9.0")
}
