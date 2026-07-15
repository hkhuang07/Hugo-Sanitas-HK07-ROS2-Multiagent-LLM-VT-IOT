idf_component_register(
    SRCS
        "main.cpp"
        "sensor_hub.cpp"
        "can_bootloader.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        freertos
        log
        esp_adc
        i2c
)
