package com.hk07.common.exception;

/** Thrown when a business rule is violated */
public class HK07BusinessException extends RuntimeException {
    public HK07BusinessException(String message) {
        super(message);
    }
}
