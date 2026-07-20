package com.taxerp.service;

import com.taxerp.dto.ERIRequest;
import com.taxerp.dto.ERIResponse;
import com.taxerp.exception.ERIApiException;

/**
 * Service interface for ERI (e-Return Intermediary) API operations.
 * Provides methods for secure communication with ITD ERI endpoints.
 */
public interface ERIApiClient {

    /**
     * Makes a test call to the ERI API with a signed payload.
     * Used for UAT verification and connectivity testing.
     *
     * @param signedPayload The digitally signed payload to send to ERI
     * @return ERIResponse containing the API response
     * @throws ERIApiException if the API call fails
     */
    ERIResponse makeTestCall(String signedPayload) throws ERIApiException;

    /**
     * Submits data to the ERI API for processing.
     * Used for actual tax return submission and other ERI operations.
     *
     * @param request The ERI request containing data and signature
     * @return ERIResponse containing the API response
     * @throws ERIApiException if the API call fails
     */
    ERIResponse submitData(ERIRequest request) throws ERIApiException;

    /**
     * Validates the ERI API connectivity and configuration.
     * Performs a health check against the ERI endpoints.
     *
     * @return true if ERI API is accessible and responding
     * @throws ERIApiException if connectivity validation fails
     */
    boolean validateConnectivity() throws ERIApiException;

    /**
     * Gets the current ERI API configuration status.
     * Provides information about endpoints, timeouts, and retry settings.
     *
     * @return Configuration status information
     */
    String getConfigurationStatus();
}