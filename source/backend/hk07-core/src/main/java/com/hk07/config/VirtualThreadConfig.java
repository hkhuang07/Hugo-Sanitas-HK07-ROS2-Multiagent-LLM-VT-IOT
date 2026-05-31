package com.hk07.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.task.AsyncTaskExecutor;
import org.springframework.core.task.support.TaskExecutorAdapter;
import org.springframework.scheduling.annotation.AsyncConfigurer;

import java.util.concurrent.Executors;

/**
 * Virtual Thread Configuration — Java 21
 *
 * Instead of creating OS-level platform threads (expensive on 1.6GHz CPU),
 * Virtual Threads are mounted/unmounted on carrier threads by the JVM scheduler.
 * This allows processing thousands of concurrent MQTT sensor streams + WebSocket
 * connections without spawning thousands of OS threads.
 *
 * Throughput for sensor processing: O(1000s) concurrent streams
 * Memory per virtual thread: ~1KB (vs ~1MB per platform thread)
 */
@Configuration
public class VirtualThreadConfig implements AsyncConfigurer {

    /**
     * All @Async methods in the application will use Virtual Threads.
     * Critical for MQTT message processing & AI API calls (I/O bound operations).
     */
    @Bean(name = "applicationTaskExecutor")
    @Override
    public AsyncTaskExecutor getAsyncExecutor() {
        // Virtual Thread per task executor — zero queuing overhead
        return new TaskExecutorAdapter(
            Executors.newVirtualThreadPerTaskExecutor()
        );
    }

    /**
     * Tomcat server thread pool override.
     * All incoming HTTP requests will also use virtual threads.
     * This is the key to handling 60Hz WebSocket data without thread starvation.
     */
    @Bean
    public org.springframework.boot.web.embedded.tomcat.TomcatProtocolHandlerCustomizer<?>
    tomcatVirtualThreadCustomizer() {
        return protocolHandler ->
            protocolHandler.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
    }
}
