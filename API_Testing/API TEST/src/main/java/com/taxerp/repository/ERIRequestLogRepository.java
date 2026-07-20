package com.taxerp.repository;

import com.taxerp.entity.ERIRequestLog;
import com.taxerp.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository interface for ERIRequestLog entity operations.
 * Provides standard CRUD operations and custom query methods for audit trail management.
 */
@Repository
public interface ERIRequestLogRepository extends JpaRepository<ERIRequestLog, UUID> {

    /**
     * Find request log by correlation ID.
     *
     * @param correlationId the correlation ID to search for
     * @return Optional containing the request log if found
     */
    Optional<ERIRequestLog> findByCorrelationId(String correlationId);

    /**
     * Find all request logs for a specific user.
     *
     * @param user the user to search for
     * @return List of request logs for the user
     */
    List<ERIRequestLog> findByUser(User user);

    /**
     * Find request logs by user ID.
     *
     * @param userId the user ID to search for
     * @return List of request logs for the user
     */
    List<ERIRequestLog> findByUserId(UUID userId);

    /**
     * Find request logs by endpoint.
     *
     * @param endpoint the endpoint to search for
     * @return List of request logs for the endpoint
     */
    List<ERIRequestLog> findByEndpoint(String endpoint);

    /**
     * Find request logs by HTTP method.
     *
     * @param httpMethod the HTTP method to search for
     * @return List of request logs for the HTTP method
     */
    List<ERIRequestLog> findByHttpMethod(String httpMethod);

    /**
     * Find request logs created within a date range.
     *
     * @param startDate the start date
     * @param endDate the end date
     * @return List of request logs within the date range
     */
    List<ERIRequestLog> findByCreatedAtBetween(LocalDateTime startDate, LocalDateTime endDate);

    /**
     * Find request logs for a user within a date range.
     *
     * @param user the user
     * @param startDate the start date
     * @param endDate the end date
     * @return List of request logs for the user within the date range
     */
    List<ERIRequestLog> findByUserAndCreatedAtBetween(User user, LocalDateTime startDate, LocalDateTime endDate);

    /**
     * Find request logs by endpoint and date range, ordered by creation date descending.
     *
     * @param endpoint the endpoint
     * @param startDate the start date
     * @param endDate the end date
     * @return List of request logs ordered by creation date descending
     */
    @Query("SELECT r FROM ERIRequestLog r WHERE r.endpoint = :endpoint AND r.createdAt BETWEEN :startDate AND :endDate ORDER BY r.createdAt DESC")
    List<ERIRequestLog> findByEndpointAndDateRangeOrderByCreatedAtDesc(
            @Param("endpoint") String endpoint,
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate);

    /**
     * Count request logs by user within a date range.
     *
     * @param user the user
     * @param startDate the start date
     * @param endDate the end date
     * @return Count of request logs
     */
    @Query("SELECT COUNT(r) FROM ERIRequestLog r WHERE r.user = :user AND r.createdAt BETWEEN :startDate AND :endDate")
    Long countByUserAndDateRange(@Param("user") User user, @Param("startDate") LocalDateTime startDate, @Param("endDate") LocalDateTime endDate);

    /**
     * Find recent request logs (last N records) ordered by creation date descending.
     *
     * @param limit the maximum number of records to return
     * @return List of recent request logs
     */
    @Query("SELECT r FROM ERIRequestLog r ORDER BY r.createdAt DESC LIMIT :limit")
    List<ERIRequestLog> findRecentRequestLogs(@Param("limit") int limit);
}