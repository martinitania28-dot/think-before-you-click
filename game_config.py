# ============================================================
#  CONFIGURAZIONE DEL GIOCO — Cittadinanza Digitale
#
#  ISTRUZIONI PER LE IMMAGINI:
#  Salva le foto delle opere nella cartella  public/images/
#  con i nomi indicati nel campo "image" di ogni item.
#
#  Dimensioni consigliate: 800×800 px, formato JPG o PNG.
# ============================================================

CONFIG = {
    "title":    "Think Before You Click – Art for a Safer Internet",
    "subtitle": "Match each artwork to the correct category",

    "categories": [
        {
            "id":    "rispetto",
            "label": "Online Respect & Empathy",
            "color": "#27ae60",
            "icon":  "💚",
        },
        {
            "id":    "dipendenza",
            "label": "Digital Addiction",
            "color": "#9b59b6",
            "icon":  "📱",
        },
        {
            "id":    "cyberbullismo",
            "label": "Cyberbullying",
            "color": "#e74c3c",
            "icon":  "😡",
        },
        {
            "id":    "privacy",
            "label": "Privacy",
            "color": "#3498db",
            "icon":  "🔒",
        },
        {
            "id":    "fake-news",
            "label": "Fake News",
            "color": "#f39c12",
            "icon":  "📰",
        },
    ],

    # ── OPERE ──────────────────────────────────────────────────
    # Ogni item corrisponde a una delle opere fotografate.
    # "image" = nome del file in public/images/
    # "text"  = descrizione breve visibile sotto l'immagine
    # "correct" = id della categoria corretta
    # -----------------------------------------------------------
    "items": [
        {
            "id":      "opera-01",
            "name":    "Look at me, I'm real",
            "author":  "Olducci Chiara, Palombi Arianna",
            "image":   "/opera-01.jpeg",
            "text":    "Look at me, I'm real",
            "correct": "rispetto",
        },
        {
            "id":      "opera-02",
            "name":    "The Threads of Addiction",
            "author":  "Gill Mehreet Kaur, Cristiana Sperduti",
            "image":   "/opera-02.jpeg",
            "text":    "The Threads of Addiction",
            "correct": "dipendenza",
        },
        {
            "id":      "opera-03",
            "name":    "Words Can Hurt",
            "author":  "Gill Mehreet Kaur, Cristiana Sperduti, Alice Zomparelli, Serena D'Ambrogio",
            "image":   "/opera-03.jpg",
            "text":    "Words Can Hurt",
            "correct": "cyberbullismo",
        },
        {
            "id":      "opera-04",
            "name":    "Chaos on the Internet",
            "author":  "Panici Francesco, Bejan Bedjeti",
            "image":   "/opera-04.jpeg",
            "text":    "Chaos on the Internet",
            "correct": "fake-news",
        },
        {
            "id":      "opera-05",
            "name":    "Think Before You Click",
            "author":  "Iacovacci Sofia, Bianchi Simone",
            "image":   "/opera-05.jpeg",
            "text":    "Think Before You Click",
            "correct": "privacy",
        },
        {
            "id":      "opera-06",
            "name":    "The Sea That Does Not Give Back",
            "author":  "Giuseppe Mantua, Alessandro Panella",
            "image":   "/opera-06.jpeg",
            "text":    "The Sea That Does Not Give Back",
            "correct": "privacy",
        },
        {
            "id":      "opera-07",
            "name":    "Words that Weigh Heavily",
            "author":  "Erman Tafa, Mantua Giuseppe, Panella Alessandro",
            "image":   "/opera-07.jpeg",
            "text":    "Words that Weigh Heavily",
            "correct": "cyberbullismo",
        },
        {
            "id":      "opera-08",
            "name":    "Think Before You Click (II)",
            "author":  "Iacovacci Sofia, Bianchi Simone",
            "image":   "/opera-08.jpeg",
            "text":    "Think Before You Click (II)",
            "correct": "privacy",
        },
    ],
}
