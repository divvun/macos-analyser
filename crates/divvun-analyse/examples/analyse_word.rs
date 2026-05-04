use divvun_analyse::Analyser;

fn main() {
    let mut args = std::env::args().skip(1);
    let bundle_path = args.next().expect("argument 1: bundle-sti");
    let word = args.next().expect("argument 2: ord");

    let analyser = Analyser::load(&bundle_path).expect("Klarte ikkje lasta bundle");
    let analyses = analyser.analyse(&word).expect("Analysen feila");

    if analyses.is_empty() {
        println!("Ingen analyse funnen for '{word}'");
    } else {
        for a in &analyses {
            println!("{} → lemma: {}  taggar: {}", a.wordform, a.lemma, a.tags.join(" "));
        }
    }
}
