/// Parser for VISL CG3 format emitted by divvun-runtime.
///
/// Example CG3 output:
/// ```text
/// "<mánáid>"
/// 	"mánná" N Pl Gen <W:0.000000> @>N #2->1 (sem_hum)
/// ```
///
/// Format:
/// - Cohort line: `"<wordform>"`
/// - Reading line: `\t"lemma" TAG1 TAG2 ...`
use crate::Analysis;

/// Parse CG3 output and return all readings across all cohorts.
pub fn parse_readings(_input_word: &str, cg3_output: &str) -> Vec<Analysis> {
    let mut results = Vec::new();
    let mut current_wordform: Option<String> = None;

    for line in cg3_output.lines() {
        if let Some(wordform) = parse_cohort_line(line) {
            current_wordform = Some(wordform);
        } else if let Some(analysis) = parse_reading_line(line) {
            if let Some(ref wf) = current_wordform {
                results.push(Analysis {
                    wordform: wf.clone(),
                    lemma: analysis.0,
                    tags: analysis.1,
                });
            }
        }
    }

    results
}

/// Parse a cohort line like `"<word>"` and return the word form.
fn parse_cohort_line(line: &str) -> Option<String> {
    let line = line.trim();
    // Cohort lines start with "<
    if line.starts_with('"') && line.contains("<") {
        // Format: "<wordform>" (optionally with trailing whitespace)
        let inner = line.trim_matches('"');
        if inner.starts_with('<') && inner.ends_with('>') {
            let wordform = &inner[1..inner.len() - 1];
            return Some(wordform.to_string());
        }
    }
    None
}

/// Parse a reading line like `\t"lemma" TAG1 TAG2 ...` and return (lemma, tags).
fn parse_reading_line(line: &str) -> Option<(String, Vec<String>)> {
    // Reading lines start with a tab.
    if !line.starts_with('\t') {
        return None;
    }
    let line = &line[1..]; // Remove leading tab.

    // Skip sub-readings (starting with extra tabs or special markers).
    if line.starts_with('\t') || line.starts_with(':') {
        return None;
    }

    // Lemma is the first token, surrounded by quotes.
    if !line.starts_with('"') {
        return None;
    }

    let end_quote = line[1..].find('"')? + 1;
    let lemma = line[1..end_quote].to_string();
    let rest = line[end_quote + 1..].trim();

    // Tags are whitespace-separated tokens until special markers like @, #, or <W:.
    let tags: Vec<String> = rest
        .split_whitespace()
        .take_while(|t| !t.starts_with('@') && !t.starts_with('#') && !t.starts_with("<W:"))
        .filter(|t| !t.is_empty())
        .map(|t| t.to_string())
        .collect();

    Some((lemma, tags))
}

#[cfg(test)]
mod tests {
    use super::*;

    const EXAMPLE_OUTPUT: &str = r#""<Máná>"
	"mánná" N Sg Nom <W:0.000000> @SUBJ> #1->2

"<oaidná>"
	"oaidnit" V TV Ind Prs Sg3 <W:0.000000> @+FMAINV #2->0

"<nieida>"
	"nieida" N Sg Acc <W:0.000000> @<OBJ #3->2
"#;

    #[test]
    fn test_parse_multiple_cohorts() {
        let results = parse_readings("", EXAMPLE_OUTPUT);
        assert_eq!(results.len(), 3);
        assert_eq!(results[0].wordform, "Máná");
        assert_eq!(results[0].lemma, "mánná");
        assert!(results[0].tags.contains(&"N".to_string()));
        assert!(results[0].tags.contains(&"Sg".to_string()));

        assert_eq!(results[1].lemma, "oaidnit");
        assert_eq!(results[2].lemma, "nieida");
    }

    #[test]
    fn test_lemma_only() {
        let results = parse_readings("oaidná", EXAMPLE_OUTPUT);
        let verb = results.iter().find(|a| a.wordform == "oaidná");
        assert_eq!(verb.map(|a| a.lemma.as_str()), Some("oaidnit"));
    }
}
