use tokio::time::{interval, Duration};

pub struct BuildCollector {
    interval_seconds: u64,
}

impl BuildCollector {
    pub fn new(interval_seconds: u64) -> Self {
        Self { interval_seconds }
    }

    pub async fn start(&self) {
        let mut ticker = interval(Duration::from_secs(self.interval_seconds));
        
        loop {
            ticker.tick().await;
            if let Err(e) = self.collect_builds().await {
                tracing::error!("Failed to collect builds: {}", e);
            }
        }
    }

    async fn collect_builds(&self) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        Ok(())
    }
}
