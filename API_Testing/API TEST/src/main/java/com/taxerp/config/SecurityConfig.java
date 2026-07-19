package com.taxerp.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.header.writers.ReferrerPolicyHeaderWriter;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

import java.util.Arrays;
import java.util.List;

/**
 * Security configuration for the Tax ERP application.
 * Configures HTTPS enforcement, security headers, and CORS for Phase 1.
 * Authentication will be added in future phases.
 */
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Value("${app.security.cors.allowed-origins:http://localhost:3000,http://localhost:8080}")
    private String[] allowedOrigins;

    @Value("${app.security.https-only:false}")
    private boolean httpsOnly;

    /**
     * Configure security filter chain with basic security settings for Phase 1.
     * No authentication required as per Phase 1 scope.
     */
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            // Disable CSRF for API endpoints (will be re-enabled with proper authentication in future phases)
            .csrf(AbstractHttpConfigurer::disable)
            
            // Configure CORS
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            
            // Configure security headers (Spring Security 6 compatible)
            .headers(headers -> headers
                .frameOptions(frame -> frame.deny())
                .contentTypeOptions(contentType -> {})
                .httpStrictTransportSecurity(hsts -> hsts
                    .maxAgeInSeconds(31536000)
                    .includeSubDomains(true)
                    .preload(true)
                )
                .referrerPolicy(referrer -> referrer
                    .policy(ReferrerPolicyHeaderWriter.ReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN)
                )
                .addHeaderWriter((request, response) -> {
                    // Add Content Security Policy
                    response.setHeader("Content-Security-Policy", 
                        "default-src 'self'; " +
                        "script-src 'self' 'unsafe-inline'; " +
                        "style-src 'self' 'unsafe-inline'; " +
                        "img-src 'self' data:; " +
                        "connect-src 'self' https://uat.eri.incometax.gov.in https://uatocpservices.incometax.gov.in; " +
                        "font-src 'self'; " +
                        "object-src 'none'; " +
                        "base-uri 'self'; " +
                        "form-action 'self'");
                    
                    // Add X-Content-Type-Options
                    response.setHeader("X-Content-Type-Options", "nosniff");
                    
                    // Add X-Frame-Options
                    response.setHeader("X-Frame-Options", "DENY");
                    
                    // Add Permissions Policy
                    response.setHeader("Permissions-Policy", 
                        "geolocation=(), microphone=(), camera=()");
                })
            )
            
            // Configure authorization - permit all for Phase 1 (no authentication)
            .authorizeHttpRequests(authz -> authz
                .requestMatchers("/api/health/**").permitAll()
                .requestMatchers("/api/eri/test-call").permitAll()
                .requestMatchers("/actuator/health").permitAll()
                .requestMatchers("/actuator/info").permitAll()
                .anyRequest().permitAll() // Phase 1: No authentication required
            );

        // Enforce HTTPS in production
        if (httpsOnly) {
            http.requiresChannel(channel -> 
                channel.requestMatchers(r -> r.getHeader("X-Forwarded-Proto") != null)
                       .requiresSecure());
        }

        return http.build();
    }

    /**
     * Configure CORS settings for allowed origins.
     */
    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        
        // Set allowed origins from configuration
        configuration.setAllowedOrigins(Arrays.asList(allowedOrigins));
        
        // Set allowed methods
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        
        // Set allowed headers
        configuration.setAllowedHeaders(Arrays.asList(
            "Authorization", 
            "Content-Type", 
            "X-Requested-With", 
            "Accept", 
            "Origin", 
            "Access-Control-Request-Method", 
            "Access-Control-Request-Headers",
            "X-Correlation-ID"
        ));
        
        // Allow credentials
        configuration.setAllowCredentials(true);
        
        // Set max age for preflight requests
        configuration.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", configuration);
        
        return source;
    }
}