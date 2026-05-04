use std::sync::Arc;

use divvun_runtime::{
    bundle::Bundle,
    modules::Input,
};
use once_cell::sync::OnceCell;
use serde::{Deserialize, Serialize};
use tokio::runtime::Runtime;

use crate::cg3;

static RT: OnceCell<Runtime> = OnceCell::new();

fn rt() -> &'static Runtime {
    RT.get_or_init(|| {
        Runtime::new().expect("Klarte ikkje oppretta tokio-runtime")
    })
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Analysis {
    /// Lemma (base form) of the word.
    pub lemma: String,
    /// Morphological tags (POS, number, case, etc.).
    pub tags: Vec<String>,
    /// The original word form that was analyzed.
    pub wordform: String,
}

#[derive(Debug, thiserror::Error)]
pub enum AnalyserError {
    #[error("Klarte ikkje lasta bundle: {0}")]
    BundleLoad(String),
    #[error("Analysen feila: {0}")]
    Pipeline(String),
    #[error("Tom utdata frå pipeline")]
    EmptyOutput,
}

/// A loaded analyzer instance for one language/bundle.
pub struct Analyser {
    bundle: Arc<Bundle>,
}

impl Analyser {
    /// Load a `.drb` bundle from disk.
    pub fn load(bundle_path: &str) -> Result<Self, AnalyserError> {
        let path = bundle_path.to_string();
        let bundle = rt()
            .block_on(async move {
                Bundle::from_bundle(&path).await
            })
            .map_err(|e| AnalyserError::BundleLoad(e.to_string()))?;
        Ok(Analyser {
            bundle: Arc::new(bundle),
        })
    }

    /// Analyze a word and return all readings (lemma + tags).
    pub fn analyse(&self, word: &str) -> Result<Vec<Analysis>, AnalyserError> {
        let bundle = Arc::clone(&self.bundle);
        let word = word.to_string();

        let raw = rt()
            .block_on(async move {
                let mut pipe = bundle
                    .create(serde_json::json!({}))
                    .await
                    .map_err(|e| AnalyserError::Pipeline(e.to_string()))?;

                let mut stream = pipe.forward(Input::String(word)).await;

                use futures_util::StreamExt;
                while let Some(Ok(input)) = stream.next().await {
                    match input {
                        Input::String(s) => return Ok(s),
                        Input::Bytes(b) => {
                            return String::from_utf8(b)
                                .map_err(|e| AnalyserError::Pipeline(e.to_string()));
                        }
                        _ => continue,
                    }
                }
                Err(AnalyserError::EmptyOutput)
            })?;

        Ok(cg3::parse_readings(&word_from_raw_input(word.as_str()), &raw))
    }

    /// Convenience method: return only the best lemma (first reading).
    pub fn lemmatise(&self, word: &str) -> Result<Option<String>, AnalyserError> {
        let analyses = self.analyse(word)?;
        Ok(analyses.into_iter().next().map(|a| a.lemma))
    }
}

// Helper function: preserve the original input word (needed for cohort matching in the CG3 parser).
fn word_from_raw_input(word: &str) -> String {
    word.to_string()
}
