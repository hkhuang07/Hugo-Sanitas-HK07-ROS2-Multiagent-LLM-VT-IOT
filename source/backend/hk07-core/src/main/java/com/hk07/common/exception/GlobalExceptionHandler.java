package com.hk07.common.exception;

import com.hk07.common.dto.ApiResponse;
import jakarta.validation.ConstraintViolationException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.servlet.resource.NoResourceFoundException;

import java.util.stream.Collectors;

/**
 * Centralized exception handler — captures all uncaught exceptions in the app.
 *
 * Design principle: No exception should leak raw stack traces to the client.
 * All errors are wrapped in ApiResponse with a user-friendly message.
 *
 * This is a core component of Phase 01 (Foundation) that all other phases depend on.
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /** Validation errors from @Valid annotations */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Void>> handleValidation(MethodArgumentNotValidException ex) {
        String errors = ex.getBindingResult().getFieldErrors().stream()
                .map(FieldError::getDefaultMessage)
                .collect(Collectors.joining("; "));
        log.warn("[VALIDATION_ERROR] {}", errors);
        return ResponseEntity.badRequest()
                .body(ApiResponse.error("Validation failed: " + errors));
    }

    /** Constraint violations from @Validated on service methods */
    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<ApiResponse<Void>> handleConstraintViolation(ConstraintViolationException ex) {
        String message = ex.getConstraintViolations().stream()
                .map(cv -> cv.getPropertyPath() + ": " + cv.getMessage())
                .collect(Collectors.joining("; "));
        log.warn("[CONSTRAINT_VIOLATION] {}", message);
        return ResponseEntity.badRequest()
                .body(ApiResponse.error(message));
    }

    /** Authentication failures */
    @ExceptionHandler(BadCredentialsException.class)
    public ResponseEntity<ApiResponse<Void>> handleBadCredentials(BadCredentialsException ex) {
        log.warn("[AUTH_FAILED] Bad credentials attempt");
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED)
                .body(ApiResponse.error("Invalid credentials"));
    }

    /** Authorization failures */
    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<ApiResponse<Void>> handleAccessDenied(AccessDeniedException ex) {
        log.warn("[ACCESS_DENIED] Insufficient permissions");
        return ResponseEntity.status(HttpStatus.FORBIDDEN)
                .body(ApiResponse.error("Access denied: insufficient permissions"));
    }

    /** Domain-specific "not found" errors */
    @ExceptionHandler(HK07NotFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNotFound(HK07NotFoundException ex) {
        log.warn("[NOT_FOUND] {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error(ex.getMessage()));
    }

    /** Domain-specific business logic violations */
    @ExceptionHandler(HK07BusinessException.class)
    public ResponseEntity<ApiResponse<Void>> handleBusiness(HK07BusinessException ex) {
        log.warn("[BUSINESS_ERROR] {}", ex.getMessage());
        return ResponseEntity.badRequest()
                .body(ApiResponse.error(ex.getMessage()));
    }

    /** Static resource or route not found (404) */
    @ExceptionHandler(NoResourceFoundException.class)
    public ResponseEntity<ApiResponse<Void>> handleNoResourceFound(NoResourceFoundException ex) {
        log.warn("[ROUTE_NOT_FOUND] {}", ex.getMessage());
        return ResponseEntity.status(HttpStatus.NOT_FOUND)
                .body(ApiResponse.error("Resource not found: " + ex.getMessage()));
    }

    /**
     * Catch-all handler — must NOT expose internal details.
     * Log full stack trace internally, return generic message to client.
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Void>> handleGeneric(Exception ex) {
        log.error("[UNHANDLED_EXCEPTION] {} — {}", ex.getClass().getSimpleName(), ex.getMessage(), ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error("An internal error occurred. Contact system operator."));
    }
}
