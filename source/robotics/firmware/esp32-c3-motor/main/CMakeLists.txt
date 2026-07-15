idf_component_register(
    SRCS
        "main.cpp"
        "motor_controller.cpp"
        "can_bootloader.cpp"
    INCLUDE_DIRS "."
    REQUIRES
        driver
        freertos
        log
        esp_timer
)
