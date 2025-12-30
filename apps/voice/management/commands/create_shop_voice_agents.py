"""
Management command to create ShopVoiceAgent for all existing shops.
Run this after initial migration to backfill agents for existing shops.
"""
from django.core.management.base import BaseCommand
from apps.shops.models import Shop
from apps.voice.models import ShopVoiceAgent


class Command(BaseCommand):
    help = 'Create ShopVoiceAgent for all existing shops that do not have one'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        shops = Shop.objects.filter(is_active=True)
        total_shops = shops.count()
        created_count = 0
        skipped_count = 0
        
        self.stdout.write(f"Found {total_shops} active shops")
        
        for shop in shops:
            # Check if agent already exists
            if hasattr(shop, 'voice_agent'):
                skipped_count += 1
                if options['verbosity'] >= 2:
                    self.stdout.write(f"  Skipped: {shop.name} (already has agent)")
                continue
            
            if dry_run:
                self.stdout.write(f"  Would create: {shop.name}")
                created_count += 1
            else:
                try:
                    ShopVoiceAgent.objects.create(shop=shop)
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(f"  Created: {shop.name}"))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error for {shop.name}: {e}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"\nDry run complete. Would create {created_count} agents, skip {skipped_count}."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\nCreated {created_count} ShopVoiceAgents, skipped {skipped_count}."
            ))
