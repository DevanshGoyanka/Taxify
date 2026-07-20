package com.taxerp.repository;

import com.taxerp.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * Repository interface for User entity operations.
 * Provides standard CRUD operations and custom query methods.
 */
@Repository
public interface UserRepository extends JpaRepository<User, UUID> {

    /**
     * Find user by username (case-insensitive).
     *
     * @param username the username to search for
     * @return Optional containing the user if found
     */
    Optional<User> findByUsernameIgnoreCase(String username);

    /**
     * Find user by email address.
     *
     * @param email the email to search for
     * @return Optional containing the user if found
     */
    Optional<User> findByEmail(String email);

    /**
     * Find all active users.
     *
     * @return List of active users
     */
    List<User> findByActiveTrue();

    /**
     * Find users by organization.
     *
     * @param organization the organization name
     * @return List of users in the organization
     */
    List<User> findByOrganization(String organization);

    /**
     * Check if username exists (case-insensitive).
     *
     * @param username the username to check
     * @return true if username exists, false otherwise
     */
    boolean existsByUsernameIgnoreCase(String username);

    /**
     * Check if email exists.
     *
     * @param email the email to check
     * @return true if email exists, false otherwise
     */
    boolean existsByEmail(String email);

    /**
     * Find users by full name containing the given text (case-insensitive).
     *
     * @param fullName the text to search in full names
     * @return List of matching users
     */
    @Query("SELECT u FROM User u WHERE LOWER(u.fullName) LIKE LOWER(CONCAT('%', :fullName, '%'))")
    List<User> findByFullNameContainingIgnoreCase(@Param("fullName") String fullName);
}