-- GeoCode Parcel Delivery System — MySQL schema
-- Run: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS parcel_system
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE parcel_system;

CREATE TABLE IF NOT EXISTS addresses (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    receiver_name   VARCHAR(120) NOT NULL,
    receiver_phone  VARCHAR(20)  NOT NULL UNIQUE,
    label           VARCHAR(120) NOT NULL,
    geocode         VARCHAR(10)  NOT NULL UNIQUE,
    latitude        DECIMAL(10, 6) NOT NULL,
    longitude       DECIMAL(10, 6) NOT NULL,
    qr_path         VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_phone (receiver_phone),
    INDEX idx_addr_geocode (geocode)
);

CREATE TABLE IF NOT EXISTS parcels (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    tracking_id     VARCHAR(12)  NOT NULL UNIQUE,
    address_id      INT NOT NULL,
    geocode         VARCHAR(10)  NOT NULL,
    sender_name     VARCHAR(120) NOT NULL,
    receiver_name   VARCHAR(120) NOT NULL,
    receiver_phone  VARCHAR(20)  NOT NULL,
    raw_address     VARCHAR(500) NOT NULL,
    latitude        DECIMAL(10, 6) NOT NULL,
    longitude       DECIMAL(10, 6) NOT NULL,
    status          ENUM('CREATED', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'FAILED')
                    NOT NULL DEFAULT 'CREATED',
    qr_path         VARCHAR(255),
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (address_id) REFERENCES addresses(id),
    INDEX idx_geocode (geocode),
    INDEX idx_status (status)
);

CREATE TABLE IF NOT EXISTS scan_events (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    parcel_id       INT NOT NULL,
    scanned_geocode VARCHAR(10) NOT NULL,
    resolved        BOOLEAN NOT NULL DEFAULT TRUE,
    note            VARCHAR(255),
    scanned_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parcel_id) REFERENCES parcels(id) ON DELETE CASCADE
);
