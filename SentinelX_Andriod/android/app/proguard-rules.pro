# Retrofit + kotlinx.serialization reflection-free setup needs these kept.
-keepattributes Signature, InnerClasses, EnclosingMethod, *Annotation*

-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

-dontwarn okhttp3.internal.platform.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**

# kotlinx.serialization: keep generated serializers for our DTOs.
-keepclassmembers class com.sentinelx.mobile.data.api.dto.** {
    *** Companion;
}
-keepclasseswithmembers class com.sentinelx.mobile.data.api.dto.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep class com.sentinelx.mobile.data.api.dto.**$$serializer { *; }

# Tink (via androidx.security-crypto) references errorprone/j2objc annotations
# that are compile-only; safe to ignore at R8 time.
-dontwarn com.google.errorprone.annotations.**
-dontwarn com.google.j2objc.annotations.**
-dontwarn javax.annotation.**
