#!/usr/bin/env python3
# Bot test skripti

from bot import *

def test_bot():
    print("Bot test boshlandi...")
    
    # Test 1: Importlar
    try:
        from services import SERVICES
        from regions import REGIONS
        from languages import get_texts
        print("✅ Barcha importlar muvaffaqiyatli")
    except Exception as e:
        print(f"❌ Import xatoligi: {e}")
        return
    
    # Test 2: Menu builderlar
    try:
        # Uzbek lotin
        lt_menu = build_service_menu('uz_lt')
        print(f"✅ LT menu: {len(lt_menu.keyboard)} ta xizmat")
        
        # Russian
        ru_menu = build_service_menu('ru')
        print(f"✅ RU menu: {len(ru_menu.keyboard)} ta xizmat")
        
        # Uzbek kirill
        kr_menu = build_service_menu('uz_kr')
        print(f"✅ KR menu: {len(kr_menu.keyboard)} ta xizmat")
        
    except Exception as e:
        print(f"❌ Menu builder xatoligi: {e}")
        return
    
    # Test 3: Textlar
    try:
        uz_kr_texts = get_texts('uz_kr')
        uz_lt_texts = get_texts('uz_lt')
        ru_texts = get_texts('ru')
        
        print("✅ Barcha tillar uchun textlar yuklandi")
        print(f"   KR: {uz_kr_texts['welcome']}")
        print(f"   LT: {uz_lt_texts['welcome']}")
        print(f"   RU: {ru_texts['welcome']}")
        
    except Exception as e:
        print(f"❌ Textlar xatoligi: {e}")
        return
    
    # Test 4: Xizmatlar ro'yxati
    try:
        lt_services = SERVICES['uz_lt']
        ru_services = SERVICES['ru']
        kr_services = SERVICES['uz_kr']
        
        print(f"✅ LT xizmatlar: {lt_services[:3]}")
        print(f"✅ RU xizmatlar: {ru_services[:3]}")
        print(f"✅ KR xizmatlar: {kr_services[:3]}")
        
    except Exception as e:
        print(f"❌ Xizmatlar xatoligi: {e}")
        return
    
    print("✅ Barcha testlar muvaffaqiyatli o'tdi!")

if __name__ == "__main__":
    test_bot()
