package com.hk07.common.exception;

/** Thrown when a requested resource is not found in the database */
public class HK07NotFoundException extends RuntimeException {
    public HK07NotFoundException(String message) {
        super(message);
    }
    public HK07NotFoundException(String resource, String id) {
        super(resource + " not found with id: " + id);
    }
}
