"""Genera SECRET_KEY y FERNET_KEY para copiarlas al archivo .env.

    python scripts/generar_claves.py
"""
import secrets

from cryptography.fernet import Fernet

print("Copia estas dos líneas en tu archivo .env:\n")
print(f"SECRET_KEY={secrets.token_hex(32)}")
print(f"FERNET_KEY={Fernet.generate_key().decode()}")
print("\nIMPORTANTE: todo el equipo debe usar la MISMA FERNET_KEY si comparten la base de datos;"
      " si se pierde, las contraseñas de los servidores enrolados ya no se podrán descifrar.")
