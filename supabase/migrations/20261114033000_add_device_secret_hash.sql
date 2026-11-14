-- Aplicación a cargo de mamisatow. Los dispositivos previos quedan sin clave
-- y no pueden enviar lecturas hasta que el equipo les asigne una credencial.
alter table public.device add column secret_hash text;
