input_file = "MATINJA.txt"     # Ton fichier original
output_file = "heart.txt"  # Fichier avec les données extraites

with open(input_file, "r") as f_in, open(output_file, "w") as f_out:
    for line in f_in:
        parts = line.strip().split(",")
        if len(parts) >= 3:
            valeur = parts[2]
            f_out.write(valeur + "\n")

print("Extraction terminée.")
