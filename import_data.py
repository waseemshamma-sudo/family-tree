import pandas as pd
from app import get_db_connection, create_table_if_not_exists

def import_excel_to_neon(excel_file):
    print("⏳ جاري قراءة ملف الإكسل...")
    try:
        df = pd.read_excel(excel_file)
    except Exception as e:
        print(f"❌ خطأ في قراءة ملف الإكسل: {e}")
        return
    
    print(f"✅ تم العثور على {len(df)} سجل. جاري الرفع إلى Neon...")
    
    # التحقق من وجود جدول
    create_table_if_not_exists()
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    imported_count = 0
    skipped_count = 0
    
    for index, row in df.iterrows():
        try:
            # 1. الاسم
            name = str(row.get('الإسم', '')).strip()
            if not name or name == 'nan':
                skipped_count += 1
                continue
                
            # 2. معرف الأب (مع معالجة الشرطة - والنصوص الفارغة)
            father_id_raw = row.get('معرف الأب', 0)
            try:
                father_id = int(father_id_raw) if pd.notna(father_id_raw) else 0
            except (ValueError, TypeError):
                father_id = 0 
            
            # 3. تاريخ الميلاد
            birth = str(row.get('المواليد', '')).split(' ')[0] if pd.notna(row.get('المواليد')) else ''
            if birth == 'nan': birth = ''
            
            # 4. تاريخ الوفاة
            death = str(row.get('تاريخ الوفاة', '')).split(' ')[0] if pd.notna(row.get('تاريخ الوفاة')) else ''
            if death == 'nan': death = ''
            
            # 5. الوظيفة
            job = str(row.get('الوظيفة', ''))
            if job == 'nan': job = ''
            
            # 6. رقم الجوال
            phone = str(row.get('رقم الجوال', ''))
            if phone == 'nan': phone = ''
            
            # 7. مكان الإقامة
            location = str(row.get('بلد الإقامة', ''))
            if location == 'nan': location = ''
            
            # إدخال البيانات
            cur.execute("""
                INSERT INTO family_members (name, father_id, birth_year, death_year, job, phone, location)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (name, father_id, birth, death, job, phone, location))
            imported_count += 1
            
        except Exception as e:
            print(f"⚠️ تخطي سجل {index} بسبب خطأ: {e}")
            skipped_count += 1
            
    conn.commit()
    cur.close()
    conn.close()
    print(f"🎉 تم استيراد {imported_count} سجل بنجاح إلى قاعدة بيانات Neon!")
    if skipped_count > 0:
        print(f"⚠️ تم تخطي {skipped_count} سجل لعدم وجود بيانات صالحة.")

if __name__ == "__main__":
    # ضع مسار ملف الإكسل الخاص بك هنا
    create_table_if_not_exists()
    import_excel_to_neon("family_tree.xlsx") 