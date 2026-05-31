package com.hk07.domain.health.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class HourlySummaryDto {

    @JsonProperty("bucket_hour")
    private String bucketHour;

    @JsonProperty("avg_hr")
    private Integer avgHr;

    @JsonProperty("max_hr")
    private Integer maxHr;

    @JsonProperty("min_hr")
    private Integer minHr;

    @JsonProperty("avg_systolic")
    private Double avgSystolic;

    @JsonProperty("avg_spo2")
    private Double avgSpo2;

    @JsonProperty("avg_temp")
    private Double avgTemp;

    @JsonProperty("sample_count")
    private Integer sampleCount;

    @JsonProperty("worst_alert")
    private String worstAlert;
}
