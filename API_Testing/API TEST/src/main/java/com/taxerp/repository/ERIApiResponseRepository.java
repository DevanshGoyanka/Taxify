package com.taxerp.repository;

import com.taxerp.entity.ERIApiResponse;
import com.taxerp.entity.ERIRequestLog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository interface for ERIApiResponse entity operations.
 * Provides standard CRUD operations and custom query methods for response data access.
 */
@Repository
public interface ERIApiResponseRepository extends JpaRepository<ERIApiResponse, UUID> {

    /**
     * Find response by correlation ID.
     *
     * @param correlationId the correlation ID to search for
     * @return Optional containing the response if found
     */
    Optional<ERIApiResponse> findByCorrelationId(String correlationId);

    /**
     * Find response by request log.
     *
     * @param requestLog the request log to search for
     * @return Optional containing the response if found
     */
    Optional<ERIApiResponse> findByRequestLog(ERIRequestLog requestLog);

    /**
     * Find response by request log ID.
     *
     * @param requestLogId the request log ID to search for
     * @return Optional containing the response if found
     */
    Optional<ERIApiResponse> findByRequestLogId(UUID requestLogId);

    /**
     * Find responses by status code.
     *
     * @param statusCode the HTTP status code to search for
     * @return List of responses with the given status code
     */
    List<ERIApiResponse> findByStatusCode(Integer statusCode);

    /**
     * Find responses with errors (non-null error message).
     *
     * @return List of responses with errors
     */
    @Query("SELECT r FROM ERIApiResponse r WHERE r.errorMessage IS NOT NULL")
    List<ERIApiResponse> findResponsesWithErrors();

    /**
     * Find successful responses (status code 200-299).
     *
     * @return List of successful responses
     */
    @Query("SELECT r FROM ERIApiResponse r WHERE r.statusCode >= 200 AND r.statusCode < 300")
    List<ERIApiResponse> findSuccessfulResponses();

    /**
     * Find responses created within a date range.
     *
     * @param startDate the start date
     * @param endDate the end date
     * @return List of responses within the date range
     */
    List<ERIApiResponse> findByCreatedAtBetween(LocalDateTime startDate, LocalDateTime endDate);

    /**
     * Find responses by status code within a date range.
     *
     * @param statusCode the status code
     * @param startDate the start date
     * @param endDate the end date
     * @return List of responses matching criteria
     */
    List<ERIApiResponse> findByStatusCodeAndCreatedAtBetween(Integer statusCode, LocalDateTime startDate, LocalDateTime endDate);

    /**
     * Find slow responses (response time greater than threshold).
     *
     * @param thresholdMs the response time threshold in milliseconds
     * @return List of slow responses
     */
    @Query("SELECT r FROM ERIApiResponse r WHERE r.responseTimeMs > :thresholdMs ORDER BY r.responseTimeMs DESC")
    List<ERIApiResponse> findSlowResponses(@Param("thresholdMs") Integer thresholdMs);

    /**
     * Calculate average response time within a date range.
     *
     * @param startDate the start date
     * @param endDate the end date
     * @return Average response time in milliseconds
     */
    @Query("SELECT AVG(r.responseTimeMs) FROM ERIApiResponse r WHERE r.createdAt BETWEEN :startDate AND :endDate AND r.responseTimeMs IS NOT NULL")
    Double calculateAverageResponseTime(@Param("startDate") LocalDateTime startDate, @Param("endDate") LocalDateTime endDate);

    /**
     * Count responses by status code within a date range.
     *
     * @param statusCode the status code
     * @param startDate the start date
     * @param endDate the end date
     * @return Count of responses
     */
    @Query("SELECT COUNT(r) FROM ERIApiResponse r WHERE r.statusCode = :statusCode AND r.createdAt BETWEEN :startDate AND :endDate")
    Long countByStatusCodeAndDateRange(@Param("statusCode") Integer statusCode, @Param("startDate") LocalDateTime startDate, @Param("endDate") LocalDateTime endDate);

    /**
     * Find recent responses (last N records) ordered by creation date descending.
     *
     * @param limit the maximum number of records to return
     * @return List of recent responses
     */
    @Query("SELECT r FROM ERIApiResponse r ORDER BY r.createdAt DESC LIMIT :limit")
    List<ERIApiResponse> findRecentResponses(@Param("limit") int limit);
}