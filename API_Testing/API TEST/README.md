# ERI Tax ERP Phase 1

ERI-compliant Tax ERP system Phase 1 - Backend foundation with Digital Signature Certificate (DSC) signing capabilities and ERI API integration for the Income Tax Department of India.

## Overview

This Spring Boot application provides:
- Digital Signature Certificate (DSC) integration for tax document signing
- ERI API client for Income Tax Department integration  
- Comprehensive audit logging for compliance
- Health monitoring and system validation

Phase 1 focuses on establishing a production-grade backend foundation for UAT testing with ITD ERI services.

## Prerequisites

- Java 17 or higher
- Maven 3.8+
- PostgreSQL 12+
- Class 3 Digital Signature Certificate (.p12/.pfx format)

## Project Structure

```
src/
├── main/
│   ├── java/com/taxerp/
│   │   ├── controller/     # REST endpoints and request handling
│   │   ├── service/        # Business logic and external integrations
│   │   ├── config/         # Application and security configuration
│   │   ├── entity/         # JPA entities and database models
│   │   ├── repository/     # Data access and persistence
│   │   ├── util/           # Helper classes and utilities
│   │   └── TaxErpApplication.java
│   └── resources/
│       ├── application.yml
│       ├── application-dev.yml
│       ├── application-uat.yml
│       └── application-prod.yml
└── test/
    └── java/com/taxerp/    # Test classes
```

## Build and Run

### Build the application
```bash
mvn clean compile
```

### Run tests
```bash
mvn test
```

### Run the application
```bash
mvn spring-boot:run
```

### Package the application
```bash
mvn clean package
```

## Configuration

The application uses Spring profiles for environment-specific configuration:

- `dev` - Development environment (default)
- `uat` - User Acceptance Testing environment
- `prod` - Production environment

### Environment Variables

Required environment variables:

- `DSC_KEYSTORE_PATH` - Path to DSC keystore file (.p12/.pfx)
- `DSC_KEYSTORE_PASSWORD` - Password for DSC keystore
- `DB_HOST` - Database host
- `DB_USERNAME` - Database username  
- `DB_PASSWORD` - Database password
- `ERI_BASE_URL` - ERI API base URL

## Health Check

The application exposes a health endpoint at `/api/health` that validates:
- Database connectivity
- DSC keystore accessibility
- ERI configuration parameters

## Security

- HTTPS enforcement in production
- Secure keystore handling
- Sensitive data masking in logs
- Comprehensive audit trails

## Dependencies

Key dependencies:
- Spring Boot 3.2.1
- PostgreSQL driver
- BouncyCastle (cryptographic operations)
- HikariCP (connection pooling)
- SLF4J (logging)

## License

Proprietary - Internal use only