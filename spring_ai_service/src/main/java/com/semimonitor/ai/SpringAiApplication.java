package com.semimonitor.ai;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class SpringAiApplication {
    public static void main(String[] args) {
        SpringApplication.run(SpringAiApplication.class, args);
    }
}
