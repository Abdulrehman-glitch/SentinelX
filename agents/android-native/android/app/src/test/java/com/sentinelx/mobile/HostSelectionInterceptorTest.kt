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

    @Test
    fun `cleartext to a public host is refused even when cleartext is allowed`() {
        assertNull(HostSelectionInterceptor.normalize("http://api.example.com", true))
        assertNull(HostSelectionInterceptor.normalize("http://8.8.8.8:8000", true))
    }

    @Test
    fun `https-only build rejects explicit http and upgrades bare hosts`() {
        assertNull(HostSelectionInterceptor.normalize("http://192.168.1.50:8000", false))
        assertEquals("https://api.sentinelx.io", HostSelectionInterceptor.normalize("api.sentinelx.io", false))
    }

    @Test
    fun `private host detection covers rfc1918 loopback and local names`() {
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://192.168.0.10"))
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://10.1.2.3:8000"))
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://172.20.0.1"))
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://127.0.0.1:8000"))
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://localhost:8000"))
        assertEquals(true, HostSelectionInterceptor.isPrivateHost("http://sentinelx.local"))
        assertEquals(false, HostSelectionInterceptor.isPrivateHost("http://172.32.0.1"))
        assertEquals(false, HostSelectionInterceptor.isPrivateHost("http://example.com"))
    }
}
