package com.hiepnn.ieltstranslator.common;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * Pool cho việc chạy nền của module srs (hiện chỉ có sinh mồi nhử).
 *
 * <p>Pool nhỏ và hàng đợi có chặn là cố ý: một đợt lưu hàng loạt không được phép biến
 * thành hàng trăm call Gemini song song. Khi hàng đợi đầy, {@code CallerRunsPolicy} bắt
 * chính luồng gọi chạy tác vụ — lúc đó việc lưu từ sẽ chậm lại, và đó là hành vi mong
 * muốn hơn so với âm thầm vứt tác vụ đi.
 */
@Configuration
@EnableAsync
public class AsyncConfig {

    @Bean("srsTaskExecutor")
    public Executor srsTaskExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(1);
        executor.setMaxPoolSize(2);
        executor.setQueueCapacity(50);
        executor.setThreadNamePrefix("srs-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.initialize();
        return executor;
    }
}
