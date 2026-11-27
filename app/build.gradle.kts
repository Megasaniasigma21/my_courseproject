plugins {
    alias(libs.plugins.android.application)
}

android {
    namespace = "com.example.courseproject"
    compileSdk {
        version = release(37)
    }

    defaultConfig {
        applicationId = "com.example.courseproject"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField(
            "String",
            "BOCHKINO_API_BASE_URL",
            "\"${providers.gradleProperty("bochkinoApiBaseUrl").orElse("").get()}\""
        )
    }

    buildTypes {
        release {
            // Sign course-preview builds so they can be installed from the Android package installer.
            // Replace this with a private release key before distributing the app publicly.
            signingConfig = signingConfigs.getByName("debug")
            optimization {
                enable = false
            }
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }
    buildFeatures {
        viewBinding = true
        buildConfig = true
    }

}

dependencies {
    implementation(libs.androidx.activity.ktx)
    implementation(libs.androidx.appcompat)
    implementation(libs.androidx.drawerlayout)
    implementation(libs.androidx.constraintlayout)
    implementation(libs.androidx.core.ktx)
    implementation(libs.material)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    implementation(libs.coil)
    implementation(libs.media3.exoplayer)
    implementation(libs.media3.ui)
    testImplementation(libs.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.junit)

}
