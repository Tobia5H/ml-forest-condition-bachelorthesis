# ml-forest-condition-bachelorthesis

Dieses Repository enthält das Programmierprojekt zur Bachelorarbeit "Zustandsbewertung von Wäldern mittels Satellitenbildern und Machine Learning".

## Installation

Um das Programm zu nutzen, installieren Sie bitte die notwendigen Pakete, indem Sie die `requirements.txt` Datei ausführen:

```bash
pip install -r requirements.txt
```

Das Modell verwendet jetzt **Detectree2**, welches Sie unter folgendem Link finden:
[Detectree2 auf GitHub](https://github.com/PatBall1/detectree2).

Bitte beachten Sie, dass das Programm nur auf Linux-basierten Systemen läuft.

## Funktionalität

Derzeit bietet das Programm folgende Funktionen:

- Eine interaktive Karte zur Auswahl der zu evaluierenden Gebiete.
- NDVI Parameteranalyse zur Bewertung des Waldzustands.
- Aufteilen großer Gebiete in kleinere, analysierbare Bereiche.
- Nutzung des vortrainierten Modells des DeepForest Frameworks.

## ToDo

- Weitere Optimierungen und Tests auf verschiedenen Linux-basierten Systemen.
- Verbesserungen in der Benutzerfreundlichkeit der interaktiven Karte.
