package com.taxerp.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.data.jpa.repository.config.EnableJpaRepositories;
import org.springframework.orm.jpa.JpaTransactionManager;
import org.springframework.orm.jpa.LocalContainerEntityManagerFactoryBean;
import org.springframework.orm.jpa.vendor.HibernateJpaVendorAdapter;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;

import javax.sql.DataSource;
import java.util.Properties;

/**
 * Database configuration for PostgreSQL with HikariCP connection pooling.
 * Configures JPA/Hibernate settings and transaction management.
 */
@Configuration
@EnableTransactionManagement
@EnableJpaRepositories(basePackages = "com.taxerp.repository")
public class DatabaseConfig {

    @Value("${spring.datasource.url}")
    private String jdbcUrl;

    @Value("${spring.datasource.username}")
    private String username;

    @Value("${spring.datasource.password}")
    private String password;

    @Value("${spring.datasource.driver-class-name:org.postgresql.Driver}")
    private String driverClassName;

    // HikariCP Configuration
    @Value("${spring.datasource.hikari.maximum-pool-size:20}")
    private int maximumPoolSize;

    @Value("${spring.datasource.hikari.minimum-idle:5}")
    private int minimumIdle;

    @Value("${spring.datasource.hikari.connection-timeout:30000}")
    private long connectionTimeout;

    @Value("${spring.datasource.hikari.idle-timeout:600000}")
    private long idleTimeout;

    @Value("${spring.datasource.hikari.max-lifetime:1800000}")
    private long maxLifetime;

    @Value("${spring.datasource.hikari.leak-detection-threshold:60000}")
    private long leakDetectionThreshold;

    // JPA/Hibernate Configuration
    @Value("${spring.jpa.hibernate.ddl-auto:validate}")
    private String ddlAuto;

    @Value("${spring.jpa.show-sql:false}")
    private boolean showSql;

    @Value("${spring.jpa.properties.hibernate.format_sql:false}")
    private boolean formatSql;

    @Value("${spring.jpa.properties.hibernate.dialect:org.hibernate.dialect.PostgreSQLDialect}")
    private String hibernateDialect;

    @Value("${spring.jpa.properties.hibernate.jdbc.batch_size:25}")
    private int batchSize;

    @Value("${spring.jpa.properties.hibernate.order_inserts:true}")
    private boolean orderInserts;

    @Value("${spring.jpa.properties.hibernate.order_updates:true}")
    private boolean orderUpdates;

    @Value("${spring.jpa.properties.hibernate.jdbc.batch_versioned_data:true}")
    private boolean batchVersionedData;

    /**
     * Configure HikariCP DataSource with optimized settings for PostgreSQL
     */
    @Bean
    @Primary
    public DataSource dataSource() {
        HikariConfig config = new HikariConfig();
        
        // Basic connection settings
        config.setJdbcUrl(jdbcUrl);
        config.setUsername(username);
        config.setPassword(password);
        config.setDriverClassName(driverClassName);
        
        // Pool configuration
        config.setMaximumPoolSize(maximumPoolSize);
        config.setMinimumIdle(minimumIdle);
        config.setConnectionTimeout(connectionTimeout);
        config.setIdleTimeout(idleTimeout);
        config.setMaxLifetime(maxLifetime);
        config.setLeakDetectionThreshold(leakDetectionThreshold);
        
        // Pool name for monitoring
        config.setPoolName("TaxERP-HikariCP");
        
        // Connection test query
        config.setConnectionTestQuery("SELECT 1");
        
        // PostgreSQL specific optimizations
        config.addDataSourceProperty("cachePrepStmts", "true");
        config.addDataSourceProperty("prepStmtCacheSize", "250");
        config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        config.addDataSourceProperty("useServerPrepStmts", "true");
        config.addDataSourceProperty("useLocalSessionState", "true");
        config.addDataSourceProperty("rewriteBatchedStatements", "true");
        config.addDataSourceProperty("cacheResultSetMetadata", "true");
        config.addDataSourceProperty("cacheServerConfiguration", "true");
        config.addDataSourceProperty("elideSetAutoCommits", "true");
        config.addDataSourceProperty("maintainTimeStats", "false");
        
        // SSL configuration for production
        config.addDataSourceProperty("sslmode", "prefer");
        config.addDataSourceProperty("sslfactory", "org.postgresql.ssl.DefaultJavaSSLFactory");
        
        return new HikariDataSource(config);
    }

    /**
     * Configure JPA EntityManagerFactory with Hibernate
     */
    @Bean
    public LocalContainerEntityManagerFactoryBean entityManagerFactory(DataSource dataSource) {
        LocalContainerEntityManagerFactoryBean em = new LocalContainerEntityManagerFactoryBean();
        em.setDataSource(dataSource);
        em.setPackagesToScan("com.taxerp.entity");
        
        HibernateJpaVendorAdapter vendorAdapter = new HibernateJpaVendorAdapter();
        em.setJpaVendorAdapter(vendorAdapter);
        
        Properties properties = new Properties();
        
        // Basic Hibernate properties
        properties.setProperty("hibernate.dialect", hibernateDialect);
        properties.setProperty("hibernate.hbm2ddl.auto", ddlAuto);
        properties.setProperty("hibernate.show_sql", String.valueOf(showSql));
        properties.setProperty("hibernate.format_sql", String.valueOf(formatSql));
        
        // Performance optimizations
        properties.setProperty("hibernate.jdbc.batch_size", String.valueOf(batchSize));
        properties.setProperty("hibernate.order_inserts", String.valueOf(orderInserts));
        properties.setProperty("hibernate.order_updates", String.valueOf(orderUpdates));
        properties.setProperty("hibernate.jdbc.batch_versioned_data", String.valueOf(batchVersionedData));
        
        // Connection and transaction settings
        properties.setProperty("hibernate.connection.provider_disables_autocommit", "true");
        properties.setProperty("hibernate.query.fail_on_pagination_over_collection_fetch", "true");
        properties.setProperty("hibernate.query.in_clause_parameter_padding", "true");
        
        // Caching configuration (second-level cache disabled for Phase 1)
        properties.setProperty("hibernate.cache.use_second_level_cache", "false");
        properties.setProperty("hibernate.cache.use_query_cache", "false");
        
        // Statistics and monitoring
        properties.setProperty("hibernate.generate_statistics", "false");
        
        // UUID generation strategy
        properties.setProperty("hibernate.id.new_generator_mappings", "true");
        properties.setProperty("hibernate.id.optimizer.pooled.prefer_lo", "true");
        
        // Time zone configuration
        properties.setProperty("hibernate.jdbc.time_zone", "UTC");
        
        em.setJpaProperties(properties);
        
        return em;
    }

    /**
     * Configure JPA Transaction Manager
     */
    @Bean
    public PlatformTransactionManager transactionManager(LocalContainerEntityManagerFactoryBean entityManagerFactory) {
        JpaTransactionManager transactionManager = new JpaTransactionManager();
        transactionManager.setEntityManagerFactory(entityManagerFactory.getObject());
        
        // Transaction timeout (30 seconds default)
        transactionManager.setDefaultTimeout(30);
        
        // Rollback on commit failure
        transactionManager.setRollbackOnCommitFailure(true);
        
        return transactionManager;
    }
}