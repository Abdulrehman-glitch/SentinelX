import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "com.sentinelx.mobile"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.sentinelx.mobile"
        minSdk = 26
        targetSdk = 35
        versionCode = 7
        versionName = "2.1.0"
    }

    // Signing secrets live outside source control: android/keystore.properties
    // (see keystore.properties.example) or KEYSTORE_* environment variables in CI.
    val keystoreProps = Properties().apply {
        val f = rootProject.file("keystore.properties")
        if (f.exists()) f.inputStream().use { load(it) }
    }

    fun signingValue(key: String, env: String): String? =
        keystoreProps.getProperty(key) ?: System.getenv(env)

    val releaseStorePassword = signingValue("storePassword", "KEYSTORE_STORE_PASSWORD")
    val releaseKeyAlias = signingValue("keyAlias", "KEYSTORE_KEY_ALIAS")
    val releaseKeyPassword = signingValue("keyPassword", "KEYSTORE_KEY_PASSWORD")
    val releaseStoreFile = signingValue("storeFile", "KEYSTORE_FILE") ?: "keystore/sentinelx-release.keystore"
    val releaseSigningAvailable =
        releaseStorePassword != null && releaseKeyAlias != null && releaseKeyPassword != null &&
            rootProject.file(releaseStoreFile).exists()

    signingConfigs {
        if (releaseSigningAvailable) {
            create("release") {
                storeFile = rootProject.file(releaseStoreFile)
                storePassword = releaseStorePassword
                keyAlias = releaseKeyAlias
                keyPassword = releaseKeyPassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Unsigned release bundles still build without local secrets.
            if (releaseSigningAvailable) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.security.crypto)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)

    testImplementation(libs.junit)
}
