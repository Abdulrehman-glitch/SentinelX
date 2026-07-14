package com.sentinelx.mobile

import com.sentinelx.mobile.data.api.HostSelectionInterceptor
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class HostSelectionInterceptorTest {

    @Test
    fun `blank url is rejected`() {
        assertNull(HostSelectionInterceptor.normalize(""))
        assertNull(HostSelectionInterceptor.normalize("   "))
    }

    @Test
    fun `bare host gets http scheme`() {
        assertEquals("http://192.168.1.50:8000", HostSelectionInterceptor.normalize("192.168.1.50:8000"))
    }

    @Test
    fun `existing scheme is preserved`() {
        assertEquals("https://api.sentinelx.io", HostSelectionInterceptor.normalize("https://api.sentinelx.io"))
        assertEquals("http://10.0.2.2:8000", HostSelectionInterceptor.normalize("http://10.0.2.2:8000"))
    }

    @Test
    fun `trailing slashes are stripped`() {
        assertEquals("http://10.0.2.2:8000", HostSelectionInterceptor.normalize("http://10.0.2.2:8000///"))
    }
}
