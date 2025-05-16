#!/bin/bash

# Arrêter tous les processus Xvfb existants
pkill Xvfb || true

# Attendre que les processus soient bien arrêtés
sleep 2

# Essayer différents displays
for display in 99 1 2 3 4 5; do
    echo "Tentative avec le display :$display"
    
    # Démarrer Xvfb
    Xvfb :$display -screen 0 1920x1080x24 &
    XVFB_PID=$!
    
    # Attendre que Xvfb démarre
    sleep 2
    
    # Vérifier si Xvfb a démarré correctement
    if ps -p $XVFB_PID > /dev/null; then
        echo "Xvfb démarré avec succès sur le display :$display"
        export DISPLAY=:$display
        break
    else
        echo "Échec du démarrage sur le display :$display"
        kill $XVFB_PID 2>/dev/null || true
    fi
done

# Vérifier si un display est disponible
if [ -z "$DISPLAY" ]; then
    echo "Erreur: Impossible de démarrer Xvfb sur aucun display"
    exit 1
fi

# Lancer l'application
python app.py

# Nettoyage à la fin
kill $XVFB_PID 