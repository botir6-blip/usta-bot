from bot import *

def test():
    print("Bot test started...")
    
    # Test imports
    try:
        from services import SERVICES
        from regions import REGIONS
        from languages import get_texts
        print("All imports successful")
    except Exception as e:
        print(f"Import error: {e}")
        return
    
    # Test menu builders
    try:
        lt_menu = build_service_menu('uz_lt')
        print(f"LT menu: {len(lt_menu.keyboard)} items")
        
        ru_menu = build_service_menu('ru')
        print(f"RU menu: {len(ru_menu.keyboard)} items")
        
        kr_menu = build_service_menu('uz_kr')
        print(f"KR menu: {len(kr_menu.keyboard)} items")
        
    except Exception as e:
        print(f"Menu builder error: {e}")
        return
    
    # Test texts
    try:
        uz_kr_texts = get_texts('uz_kr')
        uz_lt_texts = get_texts('uz_lt')
        ru_texts = get_texts('ru')
        
        print("Texts loaded successfully")
        print(f"KR: {uz_kr_texts['welcome']}")
        print(f"LT: {uz_lt_texts['welcome']}")
        print(f"RU: {ru_texts['welcome']}")
        
    except Exception as e:
        print(f"Texts error: {e}")
        return
    
    # Test services
    try:
        lt_services = SERVICES['uz_lt']
        ru_services = SERVICES['ru']
        kr_services = SERVICES['uz_kr']
        
        print(f"LT services: {lt_services[:3]}")
        print(f"RU services: {ru_services[:3]}")
        print(f"KR services: {kr_services[:3]}")
        
    except Exception as e:
        print(f"Services error: {e}")
        return
    
    print("All tests passed!")

if __name__ == "__main__":
    test()
