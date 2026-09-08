from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.dateparse import parse_date, parse_datetime
from django.db.models import Avg
from django.http import HttpResponse
import csv
from .models import HealthEntry, Medication, VitalSign


@login_required
def dashboard(request):
    entries = HealthEntry.objects.filter(user=request.user)[:7]
    medications = Medication.objects.filter(user=request.user, is_active=True)
    recent_vitals = VitalSign.objects.filter(user=request.user)[:5]
    mood_avg = entries.aggregate(avg=Avg('pain_level'))
    return render(request, 'health_journal/dashboard.html', {
        'entries': entries,
        'medications': medications,
        'recent_vitals': recent_vitals,
        'mood_avg': mood_avg,
    })


@login_required
def entry_list(request):
    entries = HealthEntry.objects.filter(user=request.user)
    return render(request, 'health_journal/entry_list.html', {'entries': entries})


@login_required
def entry_create(request):
    if request.method == 'POST':
        entry = HealthEntry.objects.create(
            user=request.user,
            date=parse_date(request.POST.get('date')),
            mood=request.POST.get('mood'),
            symptoms=request.POST.get('symptoms', ''),
            medications=request.POST.get('medications', ''),
            notes=request.POST.get('notes', ''),
            sleep_hours=request.POST.get('sleep_hours') or None,
            pain_level=request.POST.get('pain_level') or None,
            weight=request.POST.get('weight') or None,
        )
        messages.success(request, 'Entrée créée avec succès.')
        return redirect('entry_list')
    return render(request, 'health_journal/entry_create.html')


@login_required
def entry_detail(request, pk):
    entry = get_object_or_404(HealthEntry, pk=pk, user=request.user)
    return render(request, 'health_journal/entry_detail.html', {'entry': entry})


@login_required
def entry_edit(request, pk):
    entry = get_object_or_404(HealthEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.date = parse_date(request.POST.get('date')) or entry.date
        entry.mood = request.POST.get('mood', entry.mood)
        entry.symptoms = request.POST.get('symptoms', entry.symptoms)
        entry.medications = request.POST.get('medications', entry.medications)
        entry.notes = request.POST.get('notes', entry.notes)
        entry.sleep_hours = request.POST.get('sleep_hours') or entry.sleep_hours
        entry.pain_level = request.POST.get('pain_level') or entry.pain_level
        entry.weight = request.POST.get('weight') or entry.weight
        entry.save()
        messages.success(request, 'Entrée modifiée.')
        return redirect('entry_list')
    return render(request, 'health_journal/entry_edit.html', {'entry': entry})


@login_required
def entry_delete(request, pk):
    entry = get_object_or_404(HealthEntry, pk=pk, user=request.user)
    if request.method == 'POST':
        entry.delete()
        messages.success(request, 'Entrée supprimée.')
        return redirect('entry_list')
    return render(request, 'health_journal/entry_delete.html', {'entry': entry})


@login_required
def medication_list(request):
    medications = Medication.objects.filter(user=request.user)
    return render(request, 'health_journal/medication_list.html', {'medications': medications})


@login_required
def medication_create(request):
    if request.method == 'POST':
        Medication.objects.create(
            user=request.user,
            name=request.POST.get('name'),
            dosage=request.POST.get('dosage'),
            frequency=request.POST.get('frequency'),
            start_date=parse_date(request.POST.get('start_date')) or None,
            end_date=parse_date(request.POST.get('end_date')) or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Médicament ajouté.')
        return redirect('medication_list')
    return render(request, 'health_journal/medication_create.html')


@login_required
def vitals_list(request):
    vitals = VitalSign.objects.filter(user=request.user)
    chart = list(reversed(vitals[:30]))
    chart_data = {
        'dates': [v.date.strftime('%d/%m') for v in chart],
        'heart_rate': [v.heart_rate if v.heart_rate is not None else None for v in chart],
        'systolic_bp': [v.systolic_bp if v.systolic_bp is not None else None for v in chart],
        'blood_sugar': [float(v.blood_sugar) if v.blood_sugar is not None else None for v in chart],
        'temperature': [float(v.temperature) if v.temperature is not None else None for v in chart],
    }
    return render(request, 'health_journal/vitals_list.html', {'vitals': vitals, 'chart': chart_data})


@login_required
def vitals_create(request):
    if request.method == 'POST':
        VitalSign.objects.create(
            user=request.user,
            date=parse_datetime(request.POST.get('date')),
            systolic_bp=request.POST.get('systolic_bp') or None,
            diastolic_bp=request.POST.get('diastolic_bp') or None,
            heart_rate=request.POST.get('heart_rate') or None,
            temperature=request.POST.get('temperature') or None,
            blood_sugar=request.POST.get('blood_sugar') or None,
            notes=request.POST.get('notes', ''),
        )
        messages.success(request, 'Signes vitaux enregistrés.')
        return redirect('vitals_list')
    return render(request, 'health_journal/vitals_create.html')


@login_required
def export_journal(request):
    """Export CSV complet du journal de santé de l'utilisateur connecté."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="journal_sante.csv"'
    response.write('\ufeff')
    writer = csv.writer(response)

    entries = HealthEntry.objects.filter(user=request.user)
    writer.writerow(['=== ENTRÉES SANTÉ ==='])
    writer.writerow(['Date', 'Humeur', 'Symptômes', 'Médicaments pris', 'Sommeil (h)', 'Douleur (0-10)', 'Poids (kg)', 'Notes'])
    for e in entries:
        writer.writerow([
            e.date.isoformat(),
            e.get_mood_display(),
            e.symptoms,
            e.medications,
            e.sleep_hours,
            e.pain_level,
            e.weight,
            e.notes,
        ])

    writer.writerow([])
    writer.writerow(['=== MÉDICAMENTS ==='])
    writer.writerow(['Nom', 'Dosage', 'Fréquence', 'Début', 'Fin', 'Actif', 'Notes'])
    for m in Medication.objects.filter(user=request.user):
        writer.writerow([
            m.name, m.dosage, m.frequency,
            m.start_date.isoformat() if m.start_date else '',
            m.end_date.isoformat() if m.end_date else '',
            'Oui' if m.is_active else 'Non',
            m.notes,
        ])

    writer.writerow([])
    writer.writerow(['=== SIGNES VITAUX ==='])
    writer.writerow(['Date', 'PA syst', 'PA diast', 'FC (bpm)', 'Temp (°C)', 'Glycémie', 'Notes'])
    for v in VitalSign.objects.filter(user=request.user):
        writer.writerow([
            v.date.strftime('%d/%m/%Y %H:%M'),
            v.systolic_bp or '',
            v.diastolic_bp or '',
            v.heart_rate or '',
            v.temperature or '',
            v.blood_sugar or '',
            v.notes,
        ])
    return response
