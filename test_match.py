import sys
import os
import utils

# En este caso, el valor es la cadena original
target_string = "GRUPO 3 - CH CATERPILLAR L5"
normalized_target = utils.normalizar_cadena(target_string)

choices = {
    normalized_target: target_string
}

query_string = "CH ADIDAS GRUPO 2 L6 (PRESENCIAL-TRAVEL)"

print(f"Query: '{query_string}'")
print(f"Target (in choices): '{target_string}'")
print(f"Normalized Target Key: '{normalized_target}'")
print("-" * 20)

# Test con threshold 85 (usado para Instructors)
print("Testing with threshold 85 (Instructors):")
match_85 = utils.fuzzy_find(query_string, choices, threshold=85)
print(f"Result: {match_85}")

# Test con threshold 75 (usado para Meetings)
print("\nTesting with threshold 70 (Meetings):")
match_70 = utils.fuzzy_find(query_string, choices, threshold=75)
print(f"Result: {match_70}")
