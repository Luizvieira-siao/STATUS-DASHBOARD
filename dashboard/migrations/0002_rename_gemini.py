from django.db import migrations


def rename_gemini(apps, schema_editor):
    Assistente = apps.get_model('dashboard', 'Assistente')
    Assistente.objects.using(schema_editor.connection.alias).filter(
        llm__iexact='Gemini',
    ).update(llm='Gemini 3.8')


class Migration(migrations.Migration):
    dependencies = [('dashboard', '0001_initial')]

    operations = [migrations.RunPython(rename_gemini, migrations.RunPython.noop)]
