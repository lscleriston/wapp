import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
from app.utils.dates import build_date_context_dict, build_date_context

class TestDateContext(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("America/Sao_Paulo")

    def test_terca_feira_13_outubro_2026(self):
        # 13/10/2026 é Terça-feira
        dt = datetime(2026, 10, 13, 10, 30, tzinfo=self.tz)
        ctx = build_date_context_dict(dt)
        
        self.assertEqual(ctx["hoje_iso"], "2026-10-13")
        self.assertEqual(ctx["ontem_iso"], "2026-10-12")
        self.assertEqual(ctx["dia_semana"], "Terça-feira")
        self.assertEqual(ctx["ano_corrente"], 2026)
        
        # A última sexta-feira antes de terça 13/10/2026 deve ser estritamente 09/10/2026
        self.assertEqual(ctx["ultimos_dias"]["Sexta-feira"], "2026-10-09")
        # A última segunda antes de terça é ontem (12/10/2026)
        self.assertEqual(ctx["ultimos_dias"]["Segunda-feira"], "2026-10-12")
        # O último sábado foi 10/10/2026
        self.assertEqual(ctx["ultimos_dias"]["Sábado"], "2026-10-10")
        # O último domingo foi 11/10/2026
        self.assertEqual(ctx["ultimos_dias"]["Domingo"], "2026-10-11")

        # Períodos
        self.assertEqual(ctx["esta_semana_inicio"], "2026-10-12")
        self.assertEqual(ctx["esta_semana_fim"], "2026-10-13")
        self.assertEqual(ctx["semana_passada_inicio"], "2026-10-05")
        self.assertEqual(ctx["semana_passada_fim"], "2026-10-11")
        self.assertEqual(ctx["este_mes_inicio"], "2026-10-01")
        self.assertEqual(ctx["mes_passado_inicio"], "2026-09-01")
        self.assertEqual(ctx["mes_passado_fim"], "2026-09-30")

    def test_domingo(self):
        # 18/10/2026 é Domingo
        dt = datetime(2026, 10, 18, 15, 0, tzinfo=self.tz)
        ctx = build_date_context_dict(dt)
        
        self.assertEqual(ctx["hoje_iso"], "2026-10-18")
        self.assertEqual(ctx["dia_semana"], "Domingo")
        # Último domingo estritamente anterior deve ser 11/10/2026 (7 dias antes)
        self.assertEqual(ctx["ultimos_dias"]["Domingo"], "2026-10-11")
        # Última sexta antes de domingo 18/10 é 16/10/2026
        self.assertEqual(ctx["ultimos_dias"]["Sexta-feira"], "2026-10-16")

    def test_primeiro_dia_do_mes(self):
        # 01/11/2026 é Domingo
        dt = datetime(2026, 11, 1, 9, 0, tzinfo=self.tz)
        ctx = build_date_context_dict(dt)
        
        self.assertEqual(ctx["hoje_iso"], "2026-11-01")
        self.assertEqual(ctx["ontem_iso"], "2026-10-31")
        self.assertEqual(ctx["este_mes_inicio"], "2026-11-01")
        self.assertEqual(ctx["mes_passado_inicio"], "2026-10-01")
        self.assertEqual(ctx["mes_passado_fim"], "2026-10-31")

    def test_virada_de_ano(self):
        # 05/01/2027 é Terça-feira
        dt = datetime(2027, 1, 5, 8, 0, tzinfo=self.tz)
        ctx = build_date_context_dict(dt)
        
        self.assertEqual(ctx["hoje_iso"], "2027-01-05")
        self.assertEqual(ctx["ano_corrente"], 2027)
        self.assertEqual(ctx["dia_semana"], "Terça-feira")
        self.assertEqual(ctx["ultimos_dias"]["Sexta-feira"], "2027-01-01")
        self.assertEqual(ctx["mes_passado_inicio"], "2026-12-01")
        self.assertEqual(ctx["mes_passado_fim"], "2026-12-31")

    def test_build_date_context_text(self):
        dt = datetime(2026, 10, 13, 10, 0, tzinfo=self.tz)
        text = build_date_context(dt)
        self.assertIn("Hoje: 2026-10-13 (Terça-feira)", text)
        self.assertIn("Última Sexta-feira: 2026-10-09", text)
        self.assertIn("Ano Corrente: 2026", text)

if __name__ == "__main__":
    unittest.main()
