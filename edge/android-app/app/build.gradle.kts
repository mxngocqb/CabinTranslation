plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "vn.cabin.translate"
    compileSdk = 35
    defaultConfig {
        applicationId = "vn.cabin.translate"
        minSdk = 29
        targetSdk = 33
        versionCode = 1
        versionName = "1.0"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")   // installable test build
        }
    }
    // the engine (libcabin_edge.so) is executed as a process, so native libs must be extracted to disk
    packaging { jniLibs { useLegacyPackaging = true } }
    androidResources { noCompress += listOf("onnx") }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}
