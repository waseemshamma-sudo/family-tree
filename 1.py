import os
import pandas as pd
from datetime import datetime
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, filters
from pathlib import Path
from dotenv import load_dotenv

# تحميل متغيرات البيئة
load_dotenv()

# إعداد التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

class FamilyBot:
    def __init__(self):
        # ===== مسار ديناميكي لقاعدة البيانات =====
        base = Path(__file__).resolve().parent
        target = base if base.name.upper() == "FAMILY" else base / "FAMILY"
        target.mkdir(parents=True, exist_ok=True)
        self.db_path = str(target / "family_tree.xlsx")
        print(f"🗄️ مسار قاعدة البيانات: {self.db_path}")

        self.user_roles = {}
        self.user_assignments = {}
        self.setup_database()
        self.setup_permission_system()
        self.setup_relationship_system()

    def setup_database(self):
        """التحقق من قاعدة البيانات وإنشاؤها إذا لم تكن موجودة"""
        try:
            if os.path.exists(self.db_path):
                df = pd.read_excel(self.db_path)
                print(f"✅ ملف العائلة موجود - {len(df)} سجل")
                return True
            else:
                df = pd.DataFrame(columns=[
                    'المعرف', 'الإسم', 'النسبة', 'المواليد', 'تاريخ الوفاة',
                    'المؤهل الدراسي', 'الوظيفة', 'الحالة الإجتماعية',
                    'رقم الجوال', 'مكان الميلاد', 'بلد الإقامة', 'معرف الأب'
                ])
                df.to_excel(self.db_path, index=False)
                print("✅ تم إنشاء ملف العائلة الجديد")
                return True
        except Exception as e:
            print(f"❌ خطأ في إعداد قاعدة البيانات: {e}")
            return False

    def get_next_id(self):
        """الحصول على المعرف التالي تلقائياً مع معالجة شاملة للأخطاء"""
        try:
            if not os.path.exists(self.db_path):
                print("⚠️ ملف العائلة غير موجود، سيتم البدء بالمعرف 1")
                return 1
            
            df = pd.read_excel(self.db_path)
        
            if df.empty or 'المعرف' not in df.columns:
                print("⚠️ الملف فارغ أو لا يحتوي عمود المعرف، البدء بالرقم 1")
                return 1
        
            # تنظيف البيانات: إزالة القيم الفارغة والتحقق من أنها أرقام
            df_clean = df.dropna(subset=['المعرف'])
            df_clean = df_clean[pd.to_numeric(df_clean['المعرف'], errors='coerce').notna()]
        
            if df_clean.empty:
                print("⚠️ لا توجد معرفات رقمية صالحة، البدء بالرقم 1")
                return 1
        
            # العثور على أقصى قيمة معرف
            max_id = df_clean['المعرف'].max()
        
            if pd.isna(max_id) or max_id == 0:
                print("⚠️ المعرف الأقصى غير صالح، البدء بالرقم 1")
                return 1
        
            next_id = int(max_id) + 1
            print(f"✅ تم توليد المعرف التالي: {next_id} (بعد {int(max_id)})")
            return next_id
        
        except Exception as e:
            print(f"❌ خطأ غير متوقع في get_next_id: {e}")
            return 1

    def setup_permission_system(self):
        """إعداد نظام الصلاحيات المتكامل"""
        self.user_roles = {
            'viewer': ['view'],
            'editor': ['view', 'add', 'edit_own'],
            'admin': ['view', 'add', 'edit_all', 'delete'],
            'super_admin': ['view', 'add', 'edit_all', 'delete', 'manage_users']
        }

        # تعيين أدوار افتراضية للمستخدمين
        self.user_assignments = {
            1919573036: 'admin',  # ضع هنا ID المستخدم الرئيسي
        }
        
        print("✅ تم تهيئة نظام الصلاحيات بنجاح")

    def setup_relationship_system(self):
        """إعداد نظام صلة القرابة"""
        self.relationship_types = {
            (1, 0): "الأب",
            (0, 1): "الابن",
            (2, 0): "الجد",
            (0, 2): "الحفيد",
            (1, 1): "الأخ",
            (2, 1): "العم",
            (1, 2): "ابن الأخ",
            (2, 2): "ابن العم",
            (3, 3): "أبناء عم من الدرجة الثانية",
            (4, 4): "أبناء عم من الدرجة الثالثة",
            (5, 5): "أبناء عم من الدرجة الرابعة"
        }
        
    def check_permission(self, user_id, action):
        """التحقق من صلاحية المستخدم مع نظام الأدوار"""
        user_role = self.user_assignments.get(user_id, 'viewer')
        return action in self.user_roles.get(user_role, ['view'])
    
    def get_father_name(self, father_id):
        """استرجاع اسم الأب من معرف الأب"""
        if pd.isna(father_id) or father_id == 0 or father_id == '0':
            return ""
        
        try:
            df = pd.read_excel(self.db_path)
            father_df = df[df['المعرف'] == int(father_id)]
            if not father_df.empty:
                return str(father_df.iloc[0]['الإسم'])
            return ""
        except:
            return ""
    
    def format_phone_number(self, phone):
        """تنسيق رقم الجوال"""
        if pd.isna(phone) or phone == '':
            return None
        
        phone_str = str(phone).split('.')[0]
        if len(phone_str) == 10 and phone_str.startswith('5'):
            return f"0{phone_str}"
        elif len(phone_str) == 9 and phone_str.startswith('5'):
            return f"0{phone_str}"
        return phone_str
    
    def calculate_age(self, birth_date, death_date=None):
        """حساب العمر من تاريخ الميلاد حتى تاريخ الوفاة (إذا وجد) أو حتى اليوم"""
        if pd.isna(birth_date) or birth_date == '':
            return None
        
        try:
            if isinstance(birth_date, str):
                birth_date = datetime.strptime(birth_date, '%Y-%m-%d')
            elif isinstance(birth_date, datetime):
                pass
            else:
                birth_date = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(birth_date) - 2)
            
            # تحديد تاريخ النهاية
            if death_date and pd.notna(death_date):
                if isinstance(death_date, str):
                    end_date = datetime.strptime(death_date, '%Y-%m-%d')
                elif isinstance(death_date, datetime):
                    end_date = death_date
                else:
                    end_date = datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(death_date) - 2)
            else:
                end_date = datetime.now()
            
            age = end_date.year - birth_date.year
            
            if end_date.month < birth_date.month or (end_date.month == birth_date.month and end_date.day < birth_date.day):
                age -= 1
            
            return age
        except:
            return None
    
    def format_date(self, date):
        """تنسيق التاريخ"""
        if pd.isna(date) or date == '':
            return None
        
        try:
            if isinstance(date, str):
                return date.split(' ')[0]
            elif isinstance(date, datetime):
                return date.strftime('%Y-%m-%d')
            else:
                return datetime.fromordinal(datetime(1900, 1, 1).toordinal() + int(date) - 2).strftime('%Y-%m-%d')
        except:
            return str(date).split(' ')[0] if pd.notna(date) else None
    
    def format_person_details(self, person):
        """تنسيق تفاصيل الشخص بشكل جميل مع الترتيب حسب الميلاد"""
        df = pd.read_excel(self.db_path)
        
        # البيانات الأساسية
        name = str(person['الإسم']) if pd.notna(person['الإسم']) else ""
        person_id = str(person['المعرف']) if pd.notna(person['المعرف']) else "0"
        nasab = str(person['النسبة']) if pd.notna(person['النسبة']) else "شما"
        
        # معلومات الأب والجد
        father_name = self.get_father_name(person['معرف الأب'])
        father_info = df[df['المعرف'] == person['معرف الأب']]
        grandfather_name = ""
        if not father_info.empty and pd.notna(father_info.iloc[0]['معرف الأب']):
            grandfather_name = self.get_father_name(father_info.iloc[0]['معرف الأب'])
        
        # بناء الرسالة
        message = f"**التقرير المفصل لـ**\n"
        message += f"👤 **{name} {father_name} {grandfather_name} {nasab}**\n\n"
        
        # 📋 المعلومات الشخصية
        personal_info = "📋 **المعلومات الشخصية:**\n"
        personal_info += f"• **المعرف:** **{person_id}**\n"
        
        birth_date = self.format_date(person['المواليد'])
        if birth_date:
            # عرض السنة فقط
            birth_year = birth_date.split('-')[0] if '-' in birth_date else birth_date
            personal_info += f"• **تاريخ الميلاد:** **{birth_year}**\n"
        
        # معالجة حالة الوفاة
        death_date = self.format_date(person['تاريخ الوفاة'])
        if death_date and pd.notna(person['تاريخ الوفاة']):
            age = self.calculate_age(person['المواليد'], person['تاريخ الوفاة'])
            death_year = death_date.split('-')[0] if '-' in death_date else ""
            personal_info += f"• **توفي سنة {death_year} عن {age} عاماً**\n"
        else:
            # إذا لم يكن متوفى، عرض العمر فقط
            age = self.calculate_age(person['المواليد'])
            if age:
                personal_info += f"• **العمر:** **{age} سنة**\n"
        
        if personal_info.count('\n') > 1:
            message += personal_info + "\n"
        
        # 👨‍👩‍👧‍👦 الحالة الاجتماعية
        social_info = "👨‍👩‍👧‍👦 **الحالة الاجتماعية:**\n"
        social_added = False
        
        if pd.notna(person['الحالة الإجتماعية']) and str(person['الحالة الإجتماعية']).strip():
            social_info += f"• **الحالة الاجتماعية:** **{person['الحالة الإجتماعية']}**\n"
            social_added = True

        # عدد الأبناء الذكور مع الترتيب حسب الميلاد
        children_df = df[df['معرف الأب'] == person['المعرف']]
        if not children_df.empty:
            # ترتيب الأبناء حسب تاريخ الميلاد
            children_sorted = self.sort_by_birthdate(children_df)
            
            social_info += f"• **عدد الأبناء الذكور:** **{len(children_sorted)}**\n"
            for i, (_, child) in enumerate(children_sorted.iterrows(), 1):
                child_name = str(child['الإسم']) if pd.notna(child['الإسم']) else ""
                
                # حساب العمر مع مراعاة تاريخ الوفاة
                age = self.calculate_age(child['المواليد'], child['تاريخ الوفاة'])
                birth_date_child = self.format_date(child['المواليد'])
                death_date_child = self.format_date(child['تاريخ الوفاة'])
                
                if birth_date_child:
                    birth_year = birth_date_child.split('-')[0] if '-' in birth_date_child else birth_date_child
                    if pd.notna(child['تاريخ الوفاة']) and death_date_child:
                        social_info += f"**{i}- {child_name}  /  تولد {birth_year} / توفي عن {age} عاماً**\n"
                    elif age:
                        social_info += f"**{i}- {child_name}  /  تولد {birth_year} / {age} سنة**\n"
                    else:
                        social_info += f"**{i}- {child_name}  /  تولد {birth_year}**\n"
                else:
                    if pd.notna(child['تاريخ الوفاة']) and death_date_child:
                        social_info += f"**{i}- {child_name}  /  توفي عن {age} عاماً**\n"
                    elif age:
                        social_info += f"**{i}- {child_name}  /  {age} سنة**\n"
                    else:
                        social_info += f"**{i}- {child_name}**\n"
            social_added = True
        
        # الحصول على الإخوة الذكور مع الترتيب حسب الميلاد
        brothers = self.get_brothers(person['المعرف'], df)
        if brothers:
            social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
            social_info += f"🫂 **عدد الإخوة الذكور:** **{len(brothers)}**\n"
            for i, brother_info in enumerate(brothers, 1):
                social_info += f"**{i}- {brother_info}**\n"
            social_added = True
        
        # معلومات الأب
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
        father_info = df[df['المعرف'] == person['معرف الأب']]
        if not father_info.empty:
            father_data = father_info.iloc[0]
            father_age = self.calculate_age(father_data['المواليد'], father_data['تاريخ الوفاة'])
            father_birth_date = self.format_date(father_data['المواليد'])
            father_death_date = self.format_date(father_data['تاريخ الوفاة'])
            
            if father_birth_date:
                birth_year = father_birth_date.split('-')[0] if '-' in father_birth_date else father_birth_date
                if pd.notna(father_data['تاريخ الوفاة']) and father_death_date:
                    social_info += f"👨🏻‍🍼 **الأب:**\n    **{father_name}  /  تولد {birth_year} / توفي عن {father_age} عاماً**\n"
                elif father_age:
                    social_info += f"👨🏻‍🍼 **الأب:**\n    **{father_name}  /  تولد {birth_year} / {father_age} سنة**\n"
                else:
                    social_info += f"👨🏻‍🍼 **الأب:**\n    **{father_name}  /  تولد {birth_year}**\n"
            else:
                if pd.notna(father_data['تاريخ الوفاة']) and father_death_date:
                    social_info += f"👨🏻‍🍼 **الأب:**\n    **{father_name}  /  توفي عن {father_age} عاماً**\n"
                elif father_age:
                    social_info += f"👨🏻‍🍼 **الأب:**\n    **{father_name}  /  {father_age} سنة**\n"
                else:
                    social_info += f"• **الأب:**\n    **{father_name}**\n"
        else:
            social_info += f"• **الأب:**\n    **{father_name}**\n"
        
        # الحصول على الأعمام مع الترتيب حسب الميلاد
        uncles = self.get_uncles(person['المعرف'], df)
        if uncles:
            social_info += "• **الأعمام:**\n"
            for i, uncle_info in enumerate(uncles, 1):
                social_info += f"**{i}- {uncle_info}**\n"
            social_added = True
        
        if social_added:
            message += social_info + "\n"
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
        # 👶 الأحفاد الذكور
        grandchildren = self.get_grandchildren(person['المعرف'], df)
        if grandchildren:
            message += "👶 **الأحفاد الذكور:**\n"
            message += f"• **عدد الأحفاد:** **{len(grandchildren)}**\n"
            
            for item in grandchildren:
                counter, grandchild_name, father_name, birth_year, age = item
                
                if birth_year:
                    if age:
                        message += f"**{counter}- {grandchild_name} بن {father_name}  /  تولد {birth_year} / {age} سنة**\n"
                    else:
                        message += f"**{counter}- {grandchild_name} بن {father_name}  /  تولد {birth_year}**\n"
                else:
                    if age:
                        message += f"**{counter}- {grandchild_name} بن {father_name}  /  {age} سنة**\n"
                    else:
                        message += f"**{counter}- {grandchild_name} بن {father_name}**\n"
            message += "\n"
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
        # 📍 المعلومات المكانية
        location_info = "📍 **المعلومات المكانية:**\n"
        location_added = False
        
        phone = self.format_phone_number(person['رقم الجوال'])
        if phone:
            location_info += f"• **رقم الجوال:** **{phone}**\n"
            location_added = True
        
        if pd.notna(person['مكان الميلاد']) and str(person['مكان الميلاد']).strip():
            location_info += f"• **{self.get_country_flag(str(person['مكان الميلاد']))} مكان الميلاد:** **{person['مكان الميلاد']}**\n"
            location_added = True
        
        # التحقق إذا كان الشخص متوفى لتغيير "مكان الإقامة" إلى "مكان الوفاة"
        death_date = self.format_date(person['تاريخ الوفاة'])
        if pd.notna(person['تاريخ الوفاة']) and death_date:
            # إذا كان متوفى، نستخدم "مكان الوفاة"
            if pd.notna(person['بلد الإقامة']) and str(person['بلد الإقامة']).strip():
                country_flag = self.get_country_flag(str(person['بلد الإقامة']))
                location_info += f"• **{country_flag} مكان الوفاة:** **{person['بلد الإقامة']}**\n"
                location_added = True
            else:
                location_info += "• **🇸🇾 مكان الوفاة:** **سوريا**\n"
                location_added = True
        else:
            # إذا كان على قيد الحياة، نستخدم "مكان الإقامة"
            if pd.notna(person['بلد الإقامة']) and str(person['بلد الإقامة']).strip():
                country_flag = self.get_country_flag(str(person['بلد الإقامة']))
                location_info += f"• **{country_flag} مكان الإقامة:** **{person['بلد الإقامة']}**\n"
                location_added = True
            else:
                location_info += "• **🇸🇾 مكان الإقامة:** **سوريا**\n"
                location_added = True
        
        if location_added:
            message += location_info
        
        return message

    def get_grandchildren(self, person_id, df):
        """الحصول على قائمة الأحفاد الذكور (أبناء الأبناء) مع الترتيب التجميعي"""
        try:
            grandchildren_by_child = {}
            
            # الحصول على أبناء الشخص وترتيبهم من الأكبر للأصغر
            children = df[df['معرف الأب'] == person_id]
            children_sorted = self.sort_by_birthdate(children)
            
            for _, child in children_sorted.iterrows():
                child_name = str(child['الإسم']) if pd.notna(child['الإسم']) else "غير معروف"
                child_id = child['المعرف']
                
                # الحصول على أبناء الابن (الأحفاد) وترتيبهم من الأكبر للأصغر
                child_children = df[df['معرف الأب'] == child_id]
                child_children_sorted = self.sort_by_birthdate(child_children)
                
                grandchildren_list = []
                for _, grandchild in child_children_sorted.iterrows():
                    grandchild_name = str(grandchild['الإسم']) if pd.notna(grandchild['الإسم']) else "غير معروف"
                    
                    # حساب العمر
                    age = self.calculate_age(grandchild['المواليد'], grandchild['تاريخ الوفاة'])
                    birth_date = self.format_date(grandchild['المواليد'])
                    birth_year = birth_date.split('-')[0] if birth_date and '-' in birth_date else ""
                    
                    grandchildren_list.append((
                        grandchild_name,
                        birth_year,
                        age
                    ))
                
                # إضافة قائمة أحفاد هذا الابن إلى القائمة الرئيسية
                if grandchildren_list:
                    grandchildren_by_child[child_name] = grandchildren_list
            
            # بناء القائمة النهائية مع الترقيم المتسلسل
            all_grandchildren = []
            counter = 1
            
            for child_name, grandchildren in grandchildren_by_child.items():
                for grandchild in grandchildren:
                    all_grandchildren.append((
                        counter,
                        grandchild[0],  # اسم الحفيد
                        child_name,     # اسم الأب
                        grandchild[1],  # سنة الميلاد
                        grandchild[2]   # العمر
                    ))
                    counter += 1
            
            return all_grandchildren
            
        except Exception as e:
            logging.error(f"❌ خطأ في get_grandchildren: {e}")
            return []

    def get_brothers(self, person_id, df):
        """الحصول على قائمة الإخوة الذكور للشخص مع ترتيب حسب الميلاد"""
        try:
            current_person = df[df['المعرف'] == person_id]
            if current_person.empty:
                return []
            
            father_id = current_person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                return []
            
            brothers = df[(df['معرف الأب'] == father_id) & (df['المعرف'] != person_id)]
            
            # ترتيب الإخوة حسب تاريخ الميلاد من الأقدم للأحدث
            brothers_sorted = self.sort_by_birthdate(brothers)
            
            brother_list = []
            for _, brother in brothers_sorted.iterrows():
                brother_name = str(brother['الإسم']) if pd.notna(brother['الإسم']) else "غير معروف"
                
                # حساب العمر مع مراعاة تاريخ الوفاة
                age = self.calculate_age(brother['المواليد'], brother['تاريخ الوفاة'])
                birth_date = self.format_date(brother['المواليد'])
                death_date = self.format_date(brother['تاريخ الوفاة'])
                
                if birth_date:
                    birth_year = birth_date.split('-')[0] if '-' in birth_date else birth_date
                    if pd.notna(brother['تاريخ الوفاة']) and death_date:
                        brother_list.append(f"{brother_name}  /  تولد {birth_year} / توفي عن {age} عاماً")
                    elif age:
                        brother_list.append(f"{brother_name}  /  تولد {birth_year} / {age} سنة")
                    else:
                        brother_list.append(f"{brother_name}  /  تولد {birth_year}")
                else:
                    if pd.notna(brother['تاريخ الوفاة']) and death_date:
                        brother_list.append(f"{brother_name}  /  توفي عن {age} عاماً")
                    elif age:
                        brother_list.append(f"{brother_name}  /  {age} سنة")
                    else:
                        brother_list.append(f"{brother_name}")
            
            return brother_list
        except Exception as e:
            logging.error(f"❌ خطأ في get_brothers: {e}")
            return []

    def get_uncles(self, person_id, df):
        """الحصول على قائمة الأعمام (إخوة الأب) مع ترتيب حسب الميلاد"""
        try:
            current_person = df[df['المعرف'] == person_id]
            if current_person.empty:
                return []
            
            father_id = current_person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                return []
            
            father = df[df['المعرف'] == father_id]
            if father.empty:
                return []
            
            grandfather_id = father.iloc[0]['معرف الأب']
            if pd.isna(grandfather_id) or grandfather_id == 0:
                return []
            
            uncles = df[(df['معرف الأب'] == grandfather_id) & (df['المعرف'] != father_id)]
            
            # ترتيب الأعمام حسب تاريخ الميلاد
            uncles_sorted = self.sort_by_birthdate(uncles)
            
            uncle_list = []
            for _, uncle in uncles_sorted.iterrows():
                uncle_name = str(uncle['الإسم']) if pd.notna(uncle['الإسم']) else "غير معروف"
                
                # حساب العمر مع مراعاة تاريخ الوفاة
                age = self.calculate_age(uncle['المواليد'], uncle['تاريخ الوفاة'])
                birth_date = self.format_date(uncle['المواليد'])
                death_date = self.format_date(uncle['تاريخ الوفاة'])
                
                if pd.notna(uncle['تاريخ الوفاة']) and death_date:
                    birth_year = birth_date.split('-')[0] if birth_date and '-' in birth_date else ""
                    death_year = death_date.split('-')[0] if death_date and '-' in death_date else ""
                    uncle_list.append(f"{uncle_name} ({birth_year}-{death_year} توفي عن {age} عاماً)")
                elif birth_date:
                    birth_year = birth_date.split('-')[0] if '-' in birth_date else birth_date
                    if age:
                        uncle_list.append(f"{uncle_name}  /  تولد {birth_year} / {age} سنة")
                    else:
                        uncle_list.append(f"{uncle_name}  /  تولد {birth_year}")
                else:
                    if age:
                        uncle_list.append(f"{uncle_name}  /  {age} سنة")
                    else:
                        uncle_list.append(f"{uncle_name}")
            
            return uncle_list
        except Exception as e:
            logging.error(f"❌ خطأ في get_uncles: {e}")
            return []

    def format_person_details_brief(self, person):
        """تنسيق تفاصيل الشخص بشكل مختصر بدون أعمار"""
        df = pd.read_excel(self.db_path)
        
        # البيانات الأساسية
        name = str(person['الإسم']) if pd.notna(person['الإسم']) else ""
        person_id = str(person['المعرف']) if pd.notna(person['المعرف']) else "0"
        nasab = str(person['النسبة']) if pd.notna(person['النسبة']) else "شما"
        
        # معلومات الأب والجد
        father_name = self.get_father_name(person['معرف الأب'])
        father_info = df[df['المعرف'] == person['معرف الأب']]
        grandfather_name = ""
        if not father_info.empty and pd.notna(father_info.iloc[0]['معرف الأب']):
            grandfather_name = self.get_father_name(father_info.iloc[0]['معرف الأب'])
        
        # بناء الرسالة
        message = f"**التقرير المختصر لـ**\n"
        message += f"**👤 {name} {father_name} {grandfather_name} {nasab}**\n\n"
        
        # 📋 المعلومات الشخصية
        personal_info = "**📋 المعلومات الشخصية:**\n"
        personal_info += f"**• المعرف: {person_id}**\n"
        
        birth_date = self.format_date(person['المواليد'])
        if birth_date:
            # عرض السنة فقط
            birth_year = birth_date.split('-')[0] if '-' in birth_date else birth_date
            personal_info += f"**• تاريخ الميلاد: {birth_year}**\n"
        
        # معالجة حالة الوفاة
        death_date = self.format_date(person['تاريخ الوفاة'])
        if death_date and pd.notna(person['تاريخ الوفاة']):
            age = self.calculate_age(person['المواليد'], person['تاريخ الوفاة'])
            death_year = death_date.split('-')[0] if '-' in death_date else ""
            personal_info += f"**• توفي سنة {death_year} عن {age} عاماً**\n"
        else:
            # إذا لم يكن متوفى، عرض العمر فقط
            age = self.calculate_age(person['المواليد'])
            if age:
                personal_info += f"**• العمر: {age} سنة**\n"
        
        if personal_info.count('\n') > 1:
            message += personal_info + "\n"
        
        # 👨‍👩‍👧‍👦 الحالة الاجتماعية
        social_info = "**👨‍👩‍👧‍👦 الحالة الاجتماعية:**\n"
        social_added = False
        
        # عدد الأبناء الذكور مع الترتيب حسب الميلاد (بدون أعمار)
        children_df = df[df['معرف الأب'] == person['المعرف']]
        if not children_df.empty:
            # ترتيب الأبناء حسب تاريخ الميلاد
            children_sorted = self.sort_by_birthdate(children_df)
            
            social_info += f"**👨‍👦‍👦 عدد الأبناء الذكور: {len(children_sorted)}**\n"
            for i, (_, child) in enumerate(children_sorted.iterrows(), 1):
                child_name = str(child['الإسم']) if pd.notna(child['الإسم']) else ""
                social_info += f"**{i}- {child_name}**\n"
            social_added = True
        
        # الحصول على الإخوة الذكور مع الترتيب حسب الميلاد (بدون أعمار)
        brothers = self.get_brothers_brief(person['المعرف'], df)
        if brothers:
            social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
            social_info += f"**🫂 عدد الإخوة الذكور: {len(brothers)}**\n"
            for i, brother_info in enumerate(brothers, 1):
                social_info += f"**{i}- {brother_info}**\n"
            social_added = True
        
        # معلومات الأب (بدون أعمار)
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
        father_info = df[df['المعرف'] == person['معرف الأب']]
        if not father_info.empty:
            father_data = father_info.iloc[0]
            father_birth_date = self.format_date(father_data['المواليد'])
            
            if father_birth_date:
                birth_year = father_birth_date.split('-')[0] if '-' in father_birth_date else father_birth_date
                if pd.notna(father_data['تاريخ الوفاة']):
                    father_age = self.calculate_age(father_data['المواليد'], father_data['تاريخ الوفاة'])
                    social_info += f"**👨🏻‍🍼 الأب:**\n    **{father_name} / تولد {birth_year} / توفي عن {father_age} عاماً**\n"
                else:
                    social_info += f"**👨🏻‍🍼 الأب:**\n    **{father_name} / تولد {birth_year}**\n"
            else:
                if pd.notna(father_data['تاريخ الوفاة']):
                    father_age = self.calculate_age(father_data['المواليد'], father_data['تاريخ الوفاة'])
                    social_info += f"**👨🏻‍🍼 الأب:**\n    **{father_name} / توفي عن {father_age} عاماً**\n"
                else:
                    social_info += f"**👨🏻‍🍼 الأب:**\n    **{father_name}**\n"
        else:
            social_info += f"**• الأب:**\n  **{father_name}**\n"
        
        # الحصول على الأعمام مع الترتيب حسب الميلاد (بدون أعمار)
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"
        uncles = self.get_uncles_brief(person['المعرف'], df)
        if uncles:
            social_info += "**🫂 الأعمام:**\n"
            for i, uncle_info in enumerate(uncles, 1):
                social_info += f"**{i}- {uncle_info}**\n"
            social_added = True
        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"        
        if social_added:
            message += social_info + "\n"

        # 👶 الأحفاد الذكور (بدون أعمار)
        grandchildren = self.get_grandchildren_brief(person['المعرف'], df)
        if grandchildren:
            message += "**👶 الأحفاد الذكور:**\n"
            message += f"**• عدد الأحفاد: {len(grandchildren)}**\n"
            
            for item in grandchildren:
                counter, grandchild_name, father_name = item
                message += f"**{counter}- {grandchild_name} بن {father_name}**\n"
            message += "\n"

        social_info += "**━━━━━━━━━━━━━━━━━━━━━━━**\n"    
        # 📍 المعلومات المكانية
        location_info = "**📍 المعلومات المكانية:**\n"
        location_added = False
        
        phone = self.format_phone_number(person['رقم الجوال'])
        if phone:
            location_info += f"**• رقم الجوال: {phone}**\n"
            location_added = True
        
        if pd.notna(person['مكان الميلاد']) and str(person['مكان الميلاد']).strip():
            country_flag = self.get_country_flag(str(person['مكان الميلاد']))
            location_info += f"**• {country_flag} مكان الميلاد: {person['مكان الميلاد']}**\n"
            location_added = True
        
        # التحقق إذا كان الشخص متوفى لتغيير "مكان الإقامة" إلى "مكان الوفاة"
        death_date = self.format_date(person['تاريخ الوفاة'])
        if pd.notna(person['تاريخ الوفاة']) and death_date:
            # إذا كان متوفى، نستخدم "مكان الوفاة"
            if pd.notna(person['بلد الإقامة']) and str(person['بلد الإقامة']).strip():
                country_flag = self.get_country_flag(str(person['بلد الإقامة']))
                location_info += f"**• {country_flag} مكان الوفاة: {person['بلد الإقامة']}**\n"
                location_added = True
            else:
                location_info += "**• 🇸🇾 مكان الوفاة: سوريا**\n"
                location_added = True
        else:
            # إذا كان على قيد الحياة، نستخدم "مكان الإقامة"
            if pd.notna(person['بلد الإقامة']) and str(person['بلد الإقامة']).strip():
                country_flag = self.get_country_flag(str(person['بلد الإقامة']))
                location_info += f"**• {country_flag} مكان الإقامة: {person['بلد الإقامة']}**\n"
                location_added = True
            else:
                location_info += "**• 🇸🇾 مكان الإقامة: سوريا**\n"
                location_added = True
        
        if location_added:
            message += location_info
        
        return message

    def get_brothers_brief(self, person_id, df):
        """الحصول على قائمة الإخوة الذكور للشخص مع ترتيب حسب الميلاد (بدون أعمار)"""
        try:
            current_person = df[df['المعرف'] == person_id]
            if current_person.empty:
                return []
            
            father_id = current_person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                return []
            
            brothers = df[(df['معرف الأب'] == father_id) & (df['المعرف'] != person_id)]
            
            # ترتيب الإخوة حسب تاريخ الميلاد من الأقدم للأحدث
            brothers_sorted = self.sort_by_birthdate(brothers)
            
            brother_list = []
            for _, brother in brothers_sorted.iterrows():
                brother_name = str(brother['الإسم']) if pd.notna(brother['الإسم']) else "غير معروف"
                brother_list.append(f"{brother_name}")
            
            return brother_list
        except Exception as e:
            logging.error(f"❌ خطأ في get_brothers_brief: {e}")
            return []

    def get_uncles_brief(self, person_id, df):
        """الحصول على قائمة الأعمام (إخوة الأب) مع ترتيب حسب الميلاد (بدون أعمار)"""
        try:
            current_person = df[df['المعرف'] == person_id]
            if current_person.empty:
                return []
            
            father_id = current_person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                return []
            
            father = df[df['المعرف'] == father_id]
            if father.empty:
                return []
            
            grandfather_id = father.iloc[0]['معرف الأب']
            if pd.isna(grandfather_id) or grandfather_id == 0:
                return []
            
            uncles = df[(df['معرف الأب'] == grandfather_id) & (df['المعرف'] != father_id)]
            
            # ترتيب الأعمام حسب تاريخ الميلاد
            uncles_sorted = self.sort_by_birthdate(uncles)
            
            uncle_list = []
            for _, uncle in uncles_sorted.iterrows():
                uncle_name = str(uncle['الإسم']) if pd.notna(uncle['الإسم']) else "غير معروف"
                uncle_list.append(f"{uncle_name}")
            
            return uncle_list
        except Exception as e:
            logging.error(f"❌ خطأ في get_uncles_brief: {e}")
            return []

    def get_grandchildren_brief(self, person_id, df):
        """الحصول على قائمة الأحفاد الذكور (أبناء الأبناء) مع الترتيب التجميعي (بدون أعمار)"""
        try:
            grandchildren_by_child = {}
            
            # الحصول على أبناء الشخص وترتيبهم من الأكبر للأصغر
            children = df[df['معرف الأب'] == person_id]
            children_sorted = self.sort_by_birthdate(children)
            
            for _, child in children_sorted.iterrows():
                child_name = str(child['الإسم']) if pd.notna(child['الإسم']) else "غير معروف"
                child_id = child['المعرف']
                
                # الحصول على أبناء الابن (الأحفاد) وترتيبهم من الأكبر للأصغر
                child_children = df[df['معرف الأب'] == child_id]
                child_children_sorted = self.sort_by_birthdate(child_children)
                
                grandchildren_list = []
                for _, grandchild in child_children_sorted.iterrows():
                    grandchild_name = str(grandchild['الإسم']) if pd.notna(grandchild['الإسم']) else "غير معروف"
                    grandchildren_list.append(grandchild_name)
                
                # إضافة قائمة أحفاد هذا الابن إلى القائمة الرئيسية
                if grandchildren_list:
                    grandchildren_by_child[child_name] = grandchildren_list
            
            # بناء القائمة النهائية مع الترقيم المتسلسل
            all_grandchildren = []
            counter = 1
            
            for child_name, grandchildren in grandchildren_by_child.items():
                for grandchild in grandchildren:
                    all_grandchildren.append((
                        counter,
                        grandchild,  # اسم الحفيد
                        child_name,  # اسم الأب
                    ))
                    counter += 1
            
            return all_grandchildren
            
        except Exception as e:
            logging.error(f"❌ خطأ في get_grandchildren_brief: {e}")
            return []




    
    def get_country_flag(self, country_name):
        """إرجاع علم الدولة المناسب بناءً على اسم الدولة"""
        country_name_lower = country_name.lower().strip()
        
        # أعلام الدول العربية
        if any(word in country_name_lower for word in ['سوريا', 'سوري', 'حمص', 'syria', 'syrian']):
            return "🇸🇾"
        elif any(word in country_name_lower for word in ['سعود', 'السعودية', 'saudi', 'ksa']):
            return "🇸🇦"
        elif any(word in country_name_lower for word in ['مصر', 'مصري', 'egypt', 'egyptian']):
            return "🇪🇬"
        elif any(word in country_name_lower for word in ['تركيا', 'تركي', 'turkey', 'turkish']):
            return "🇹🇷"
        elif any(word in country_name_lower for word in ['رومانيا', 'روماني', 'romania', 'romanian']):
            return "🇷🇴"
        elif any(word in country_name_lower for word in ['أمريكا', 'امريكي', 'الولايات', 'usa', 'us', 'america']):
            return "🇺🇸"
        elif any(word in country_name_lower for word in ['بريطانيا', 'بريطاني', 'انجلترا', 'uk', 'britain', 'england']):
            return "🇬🇧"
        elif any(word in country_name_lower for word in ['كندا', 'كندي', 'canada', 'canadian']):
            return "🇨🇦"
        elif any(word in country_name_lower for word in ['أستراليا', 'استراليا', 'استرالي', 'australia', 'australian']):
            return "🇦🇺"
        else:
            return "🌍"

    def sort_by_birthdate(self, df):
        """ترتيب الأشخاص حسب تاريخ الميلاد من الأكبر للأصغر"""
        try:
            if df.empty:
                return df
            
            # نسخة من البيانات لتجنب تعديل الأصلية
            df_copy = df.copy()
            
            # تحويل تواريخ الميلاد إلى datetime للترتيب
            df_copy['مواليد_مؤقت'] = pd.to_datetime(df_copy['المواليد'], errors='coerce')
            
            # ترتيب من الأكبر للأصغر (الأقدم أولاً)
            df_sorted = df_copy.sort_values('مواليد_مؤقت', ascending=True)
            
            # إزالة العمود المؤقت
            df_sorted = df_sorted.drop('مواليد_مؤقت', axis=1)
            
            return df_sorted
        except Exception as e:
            logging.error(f"❌ خطأ في sort_by_birthdate: {e}")
            return df
    
    def create_error_keyboard(self):
        """إنشاء زر الرجوع عند الخطأ"""
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 الرجوع للقائمة الرئيسية", callback_data="back_to_main")]
        ])

    def create_main_keyboard(self, user_id=None):
        """إنشاء القائمة الرئيسية مع الصلاحيات"""
        keyboard = [
            [InlineKeyboardButton("🔎 بحث تفصيلي مع المواليد", callback_data="search_partial")],
            [InlineKeyboardButton("🔍 بحث مختصر", callback_data="search_brief")],  # الزر الجديد
            [InlineKeyboardButton("📊 إحصائيات العائلة", callback_data="show_stats")],
            [InlineKeyboardButton("🧬 صلة القرابة", callback_data="relationship_search")]
        ]

        # إضافة زر الإضافة إذا كانت هناك صلاحية
        if user_id and self.check_permission(user_id, 'add'):
            keyboard.append([InlineKeyboardButton("➕ إضافة شخص جديد", callback_data="add_person")])

        return InlineKeyboardMarkup(keyboard)
 
    
    async def start(self, update: Update, context: CallbackContext):
        """أمر البدء مع الأزرار"""
        user_id = update.effective_user.id
        welcome_text = """
مرحباً بك في بوت عائلة شما 🌳

اختر أحد الخيارات أدناه للبدء:
        """
        await update.message.reply_text(welcome_text, reply_markup=self.create_main_keyboard(user_id))
    
    async def start_edit_field(self, query, person_id, field, context: CallbackContext):
        """بدء تعديل حقل معين"""
        try:
            context.user_data['editing_field'] = field
            context.user_data['edit_person_id'] = person_id
            
            df = pd.read_excel(self.db_path)
            person = df[df['المعرف'] == person_id].iloc[0]
            
            current_value = person.get(field, '')
            
            field_names = {
                'الإسم': 'الاسم',
                'المواليد': 'تاريخ الميلاد', 
                'الوظيفة': 'الوظيفة',
                'رقم الجوال': 'رقم الجوال'
            }
            
            field_name = field_names.get(field, field)
            
            await query.edit_message_text(
                f"✏️ تعديل {field_name}\n\n"
                f"القيمة الحالية: {current_value if current_value else 'غير محدد'}\n\n"
                f"أرسل القيمة الجديدة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ إلغاء", callback_data=f"edit_{person_id}")]
                ])
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في start_edit_field: {e}")
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)}")
    
    async def start_edit_father(self, query, person_id, context: CallbackContext):
        """بدء تعديل الأب"""
        try:
            context.user_data['editing_field'] = 'معرف الأب'
            context.user_data['edit_person_id'] = person_id
            
            await query.edit_message_text(
                "🔍 ابحث عن الأب الجديد (أدخل جزء من الاسم أو '0' إذا لم يكن معروفاً):",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ إلغاء", callback_data=f"edit_{person_id}")]
                ])
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في start_edit_father: {e}")
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)}")

    async def handle_father_selection(self, query, father_id, context: CallbackContext):
        """معالجة اختيار الأب أثناء الإضافة"""
        try:
            context.user_data['new_person']['معرف الأب'] = father_id
            father_name = self.get_father_name(father_id)
            
            context.user_data['add_step'] = 'birth_date'
            
            await query.edit_message_text(
                f"✅ تم اختيار الأب: {father_name} (المعرف: {father_id})\n\n"
                f"أدخل تاريخ الميلاد (YYYY-MM-DD، أو اكتب 'تخطي'):"
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في handle_father_selection: {e}")
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)}")
    
    async def start_from_callback(self, query, context: CallbackContext):
        """عرض القائمة الرئيسية من callback"""
        user_id = query.from_user.id
        welcome_text = """
مرحباً بك في بوت عائلة شما 🌳

اختر أحد الخيارات أدناه للبدء:
        """
        await query.edit_message_text(welcome_text, reply_markup=self.create_main_keyboard(user_id))
    
    async def ask_search_name(self, query, context: CallbackContext):
        """طلب اسم للبحث"""
        keyboard = [
            [InlineKeyboardButton("🔎 بحث تفصيلي مع المواليد", callback_data="search_partial")],
            [InlineKeyboardButton("🔍 بحث مختصر", callback_data="search_brief")],  # الزر الجديد
            [InlineKeyboardButton("↩️ رجوع", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "اختر طريقة البحث:",
            reply_markup=reply_markup
        )
    
    async def ask_search_term(self, query, search_type, context: CallbackContext):
        """طلب مصطلح البحث"""
        search_types = {
            "partial": "جزء من الاسم",
            "brief": "جزء من الاسم"  # البحث المختصر
        }
        
        context.user_data['awaiting_search'] = search_type
        
        await query.edit_message_text(
            f"أدخل {search_types[search_type]} للبحث:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("↩️ إلغاء", callback_data="back_to_main")]
            ])
        )

    def extended_search(self, df, search_term):
        """البحث الموسع الذي يشمل الأحفاد"""
        # البحث عن المطابقات المباشرة
        direct_matches = df[df['الإسم'].astype(str).str.contains(search_term, na=False, case=False)]
        
        if direct_matches.empty:
            return direct_matches
        
        # إنشاء مجموعة لتخزين جميع النتائج (للتجنب التكرار)
        all_results = set()
        
        # إضافة المطابقات المباشرة
        for _, person in direct_matches.iterrows():
            all_results.add(person['المعرف'])
        
        # البحث عن أحفاد كل شخص موجود في النتائج المباشرة
        for _, person in direct_matches.iterrows():
            grandchildren = self.find_grandchildren(df, person['المعرف'])
            all_results.update(grandchildren)
        
        # إعادة البيانات الكاملة للأشخاص الموجودين في النتائج
        final_results = df[df['المعرف'].isin(all_results)]
        
        return final_results

    def find_grandchildren(self, df, person_id):
        """إيجاد جميع أحفاد الشخص (أبناء الأبناء)"""
        grandchildren = set()
        
        # إيجاد أبناء الشخص
        children = df[df['معرف الأب'] == person_id]
        
        for _, child in children.iterrows():
            # إضافة الابن نفسه
            grandchildren.add(child['المعرف'])
            
            # إيجاد أبناء الابن (الأحفاد)
            grand_children = df[df['معرف الأب'] == child['المعرف']]
            for _, grand_child in grand_children.iterrows():
                grandchildren.add(grand_child['المعرف'])
        
        return grandchildren
    
    async def handle_search_message(self, update: Update, context: CallbackContext):
        """معالجة رسائل البحث"""
        if 'awaiting_search' not in context.user_data:
            return

        search_type = context.user_data['awaiting_search']
        search_term = update.message.text
        
        try:
            if not os.path.exists(self.db_path):
                await update.message.reply_text(
                    "❌ قاعدة البيانات غير موجودة",
                    reply_markup=self.create_error_keyboard()
                )
                return
            
            df = pd.read_excel(self.db_path)
            
            if search_type in ["name", "partial", "brief"]:
                results = df[df['الإسم'].astype(str).str.contains(search_term, na=False, case=False)]
            
            if results.empty:
                await update.message.reply_text(
                    f"❌ لم يتم العثور على نتائج لـ '{search_term}'",
                    reply_markup=self.create_error_keyboard()
                )
            else:
                # حفظ نوع البحث الحالي في context
                context.user_data['current_search_type'] = search_type
                await self.show_search_results(update, context, results, search_term)
                
        except Exception as e:
            logging.error(f"❌ خطأ في handle_search_message: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ في البحث: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
        
        context.user_data.pop('awaiting_search', None)
        
    async def show_search_results(self, update: Update, context: CallbackContext, results, search_term):
        """عرض نتائج البحث مع أزرار"""
        try:
            if len(results) == 1:
                # عندما تكون هناك نتيجة واحدة، عرض التفاصيل مباشرة
                person = results.iloc[0]
                
                # تحديد نوع البحث من context
                search_type = context.user_data.get('current_search_type', 'detailed')
                
                if search_type == 'brief':
                    message = self.format_person_details_brief(person)
                else:
                    message = self.format_person_details(person)
                
                keyboard = [
                    [InlineKeyboardButton("🔍 بحث جديد", callback_data="search_partial")],
                    [InlineKeyboardButton("📊 الإحصائيات", callback_data="show_stats")],
                    [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
                ]
                
                # إضافة زر التعديل إذا كانت هناك صلاحية
                if self.check_permission(update.effective_user.id, 'edit_all'):
                    keyboard.append([InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"edit_{person['المعرف']}")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                
            else:
                df = pd.read_excel(self.db_path)
                
                message = f"🔍 وجدت {len(results)} نتيجة لـ '{search_term}':\n\n"
                keyboard = []
                
                for _, person in results.head(10).iterrows():
                    name = str(person['الإسم']) if pd.notna(person['الإسم']) else ""
                    person_id = str(person['المعرف']) if pd.notna(person['المعرف']) else "0"
                    
                    father_name = self.get_father_name(person['معرف الأب'])
                    
                    # حساب العمر للعرض في نتائج البحث
                    age = self.calculate_age(person['المواليد'], person['تاريخ الوفاة'])
                    age_text = ""
                    if age is not None:
                        if pd.notna(person['تاريخ الوفاة']):
                            age_text = f" (متوفى، {age} سنة)"
                        else:
                            age_text = f" ({age} سنة)"
                    
                    formatted_name = f"{name} بن {father_name}{age_text}"
                    
                    message += f"• {formatted_name} (المعرف: {person_id})\n"
                    keyboard.append([InlineKeyboardButton(
                        f"{name} - {person_id}{age_text}", 
                        callback_data=f"view_{person_id}"
                    )])
                
                if len(results) > 10:
                    message += f"\n... و{len(results) - 10} نتيجة أخرى"
                
                # الحصول على نوع البحث الحالي من context
                search_type = context.user_data.get('current_search_type', 'partial')
                
                if search_type == 'brief':
                    keyboard.append([InlineKeyboardButton("🔍 بحث مختصر جديد", callback_data="search_brief")])
                else:
                    keyboard.append([InlineKeyboardButton("🔍 بحث تفصيلي جديد", callback_data="search_partial")])
                
                keyboard.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")])
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(message, reply_markup=reply_markup)
                    
        except Exception as e:
            logging.error(f"❌ خطأ في show_search_results: {e}")
            await update.message.reply_text(
                f"❌ خطأ في عرض النتائج: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
    
    async def show_person_details(self, query, person_id, context: CallbackContext):
        """عرض تفاصيل الشخص من زر"""
        try:
            df = pd.read_excel(self.db_path)
            person_df = df[df['المعرف'] == int(person_id)]
            
            if person_df.empty:
                await query.edit_message_text(
                    "❌ الشخص غير موجود",
                    reply_markup=self.create_error_keyboard()
                )
                return
            
            person = person_df.iloc[0]
            
            # تحديد نوع البحث بناءً على context - إصلاح هنا
            search_type = context.user_data.get('current_search_type', 'detailed')
            
            if search_type == 'brief':
                message = self.format_person_details_brief(person)
            else:
                message = self.format_person_details(person)
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث جديد", callback_data="search_partial")],
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="show_stats")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            
            # إضافة زر التعديل إذا كانت هناك صلاحية
            if self.check_permission(query.from_user.id, 'edit_all'):
                keyboard.append([InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"edit_{person_id}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_person_details: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

    # ==================== نظام الإضافة المحسن ====================
    
    async def start_add_person(self, query, context: CallbackContext):
        """بدء عملية إضافة شخص جديد"""
        try:
            # تنظيف أي بيانات سابقة
            context.user_data.clear()
            
            # إعداد حالة الإضافة
            context.user_data['adding_person'] = True
            context.user_data['new_person'] = {}
            context.user_data['add_step'] = 'name'
            
            # توليد المعرف الجديد
            new_id = self.get_next_id()
            context.user_data['new_person']['المعرف'] = new_id
            context.user_data['new_person']['النسبة'] = 'شما'  # قيمة افتراضية
            
            print(f"🆕 بدء إضافة شخص جديد بالمعرف: {new_id}")
            
            keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🧩 بدء إضافة شخص جديد\n\n"
                f"المعرف التلقائي: {new_id}\n\n"
                f"أرسل الاسم الكامل للشخص:",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في start_add_person: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ في بدء الإضافة: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
    
    async def handle_add_person_data(self, update: Update, context: CallbackContext):
        """معالجة بيانات الإضافة"""
        if not context.user_data.get('adding_person'):
            return
        
        current_step = context.user_data.get('add_step', 'name')
        user_input = update.message.text
        
        try:
            if current_step == 'name':
                context.user_data['new_person']['الإسم'] = user_input
                context.user_data['add_step'] = 'search_father'
                await update.message.reply_text("🔍 ابحث عن الأب (أدخل جزء من الاسم أو '0' إذا لم يكن معروفاً):")
                
            elif current_step == 'search_father':
                if user_input == '0':
                    context.user_data['new_person']['معرف الأب'] = 0
                    context.user_data['add_step'] = 'birth_date'
                    await update.message.reply_text("أدخل تاريخ الميلاد (YYYY-MM-DD، أو اكتب 'تخطي'):")
                else:
                    # البحث عن الأب
                    await self.search_father_for_add(update, user_input, context)
                    
            elif current_step == 'birth_date':
                if user_input.lower() != 'تخطي':
                    # التحقق من صحة التاريخ
                    try:
                        datetime.strptime(user_input, '%Y-%m-%d')
                        context.user_data['new_person']['المواليد'] = user_input
                    except ValueError:
                        await update.message.reply_text("❌ تاريخ غير صحيح. استخدم الصيغة YYYY-MM-DD أو اكتب 'تخطي':")
                        return
                
                context.user_data['add_step'] = 'phone'
                await update.message.reply_text("أدخل رقم الجوال (اختياري، اكتب 'تخطي' للتخطي):")
                
            elif current_step == 'phone':
                if user_input and user_input.lower() != 'تخطي':
                    context.user_data['new_person']['رقم الجوال'] = user_input
                
                context.user_data['add_step'] = 'save'
                await self.preview_new_person(update, context)
                
        except Exception as e:
            logging.error(f"❌ خطأ في handle_add_person_data: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
    
    async def search_father_for_add(self, update: Update, search_term, context: CallbackContext):
        """البحث عن الأب أثناء الإضافة - الإصدار المحسن"""
        try:
            df = pd.read_excel(self.db_path)
            
            # البحث عن مطابقات
            results = df[df['الإسم'].str.contains(search_term, na=False, case=False)]
            
            if results.empty:
                await update.message.reply_text(
                    "❌ لم يتم العثور على نتائج. حاول مرة أخرى أو اكتب '0' إذا لم يكن الأب معروفاً:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ لا يوجد أب", callback_data="no_father")]
                    ])
                )
                return
            
            message = "🔍 نتائج البحث عن الأب:\n\n"
            keyboard = []
            
            for _, person in results.head(8).iterrows():
                father_name = self.get_father_name(person['معرف الأب'])
                message += f"• {person['الإسم']} بن {father_name} (المعرف: {person['المعرف']})\n"
                keyboard.append([InlineKeyboardButton(
                    f"{person['الإسم']} - {person['المعرف']}", 
                    callback_data=f"select_father_add_{person['المعرف']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔍 بحث جديد", callback_data="search_again_father")])
            keyboard.append([InlineKeyboardButton("❌ لا يوجد أب", callback_data="no_father")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"❌ خطأ في search_father_for_add: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ في البحث: {str(e)}\n\nيرجى المحاولة مرة أخرى:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 بحث جديد", callback_data="search_again_father")],
                    [InlineKeyboardButton("❌ لا يوجد أب", callback_data="no_father")]
                ])
            )
    
    async def preview_new_person(self, update: Update, context: CallbackContext):
        """عرض معاينة الشخص الجديد قبل الحفظ"""
        new_person = context.user_data['new_person']
        
        # الحصول على اسم الأب
        father_name = self.get_father_name(new_person.get('معرف الأب', 0))
        
        message = "👤 معاينة البيانات الجديدة:\n\n"
        message += f"• المعرف: {new_person['المعرف']}\n"
        message += f"• الاسم: {new_person['الإسم']}\n"
        message += f"• الأب: {father_name} (المعرف: {new_person.get('معرف الأب', 0)})\n"
        message += f"• تاريخ الميلاد: {new_person.get('المواليد', 'غير محدد')}\n"
        message += f"• رقم الجوال: {new_person.get('رقم الجوال', 'غير محدد')}\n"
        message += f"• النسبة: {new_person.get('النسبة', 'شما')}\n"
        
        message += "\nهل تريد حفظ هذه البيانات؟"
        
        keyboard = [
            [InlineKeyboardButton("✅ حفظ", callback_data="save_person")],
            [InlineKeyboardButton("✏️ تعديل", callback_data="edit_new_person")],
            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(message, reply_markup=reply_markup)
    
    async def save_new_person(self, query, context: CallbackContext):
        """حفظ الشخص الجديد في قاعدة البيانات"""
        try:
            new_person = context.user_data['new_person']
            df = pd.read_excel(self.db_path)
            
            # التحقق من صحة معرف الأب
            father_id = new_person.get('معرف الأب', 0)
            if father_id != 0:
                father_exists = df[df['المعرف'] == father_id]
                if father_exists.empty:
                    await query.edit_message_text(
                        f"❌ خطأ: معرف الأب {father_id} غير موجود في قاعدة البيانات",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔍 اختيار أب آخر", callback_data="search_again_father")],
                            [InlineKeyboardButton("❌ إلغاء", callback_data="cancel_add")]
                        ])
                    )
                    return
            
            # إنشاء الصف الجديد مع جميع الأعمدة
            new_row = {
                'المعرف': new_person['المعرف'],
                'الإسم': new_person.get('الإسم', ''),
                'النسبة': new_person.get('النسبة', 'شما'),
                'المواليد': new_person.get('المواليد', ''),
                'تاريخ الوفاة': new_person.get('تاريخ الوفاة', ''),
                'المؤهل الدراسي': new_person.get('المؤهل الدراسي', ''),
                'الوظيفة': new_person.get('الوظيفة', ''),
                'الحالة الإجتماعية': new_person.get('الحالة الإجتماعية', ''),
                'رقم الجوال': new_person.get('رقم الجوال', ''),
                'مكان الميلاد': new_person.get('مكان الميلاد', ''),
                'بلد الإقامة': new_person.get('بلد الإقامة', ''),
                'معرف الأب': new_person.get('معرف الأب', 0)
            }
            
            # إضافة الصف الجديد
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            
            # حفظ الملف
            df.to_excel(self.db_path, index=False)
            
            # تنظيف البيانات المؤقتة
            context.user_data.pop('adding_person', None)
            context.user_data.pop('new_person', None)
            context.user_data.pop('add_step', None)
            
            await query.edit_message_text(
                f"✅ تمت إضافة الشخص الجديد بنجاح\nالمعرف: {new_person['المعرف']}",
                reply_markup=self.create_main_keyboard(query.from_user.id)
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في save_new_person: {e}")
            await query.edit_message_text(
                f"❌ فشل في حفظ البيانات: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
    
    async def cancel_add_person(self, query, context: CallbackContext):
        """إلغاء عملية الإضافة"""
        context.user_data.pop('adding_person', None)
        context.user_data.pop('new_person', None)
        context.user_data.pop('add_step', None)
        
        await query.edit_message_text(
            "❌ تم إلغاء عملية الإضافة",
            reply_markup=self.create_main_keyboard(query.from_user.id)
        )

    # ==================== نظام التعديلات المحسن ====================

    async def show_person_details_message(self, update: Update, person):
        """عرض تفاصيل الشخص في رسالة مع مراعاة نوع البحث"""
        try:
            # الحصول على context من update
            context = getattr(update, '_context', None)
            
            # تحديد نوع البحث
            search_type = 'detailed'  # قيمة افتراضية
            if context and hasattr(context, 'user_data'):
                search_type = context.user_data.get('current_search_type', 'detailed')
            
            if search_type == 'brief':
                message = self.format_person_details_brief(person)
            else:
                message = self.format_person_details(person)
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث جديد", callback_data="search_partial")],
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="show_stats")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            
            # إضافة زر التعديل إذا كانت هناك صلاحية
            if hasattr(update, 'effective_user') and self.check_permission(update.effective_user.id, 'edit_all'):
                keyboard.append([InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"edit_{person['المعرف']}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_person_details_message: {e}")
            await update.message.reply_text(
                f"❌ خطأ في عرض التفاصيل: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

    async def start_edit_person(self, query, person_id, context: CallbackContext):
        """بدء عملية تعديل الشخص"""
        try:
            # التحقق من الصلاحيات
            if not self.check_permission(query.from_user.id, 'edit_all'):
                await query.edit_message_text("❌ ليس لديك صلاحية لتعديل البيانات")
                return
            
            context.user_data['editing_person'] = True
            context.user_data['edit_person_id'] = person_id
            context.user_data['edit_changes'] = {}
            
            df = pd.read_excel(self.db_path)
            person = df[df['المعرف'] == person_id].iloc[0]
            
            # عرض واجهة التعديل
            await self.show_edit_interface(query, person, context)
            
        except Exception as e:
            logging.error(f"❌ خطأ في start_edit_person: {e}")
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)}")

    async def show_edit_interface(self, query, person, context: CallbackContext):
        """عرض واجهة التعديل مع الخيارات"""
        father_name = self.get_father_name(person['معرف الأب'])
        
        message = f"✏️ تعديل بيانات {person['الإسم']} {father_name} شمّا\n\n"
        message += f"📋 البيانات الحالية:\n"
        message += f"• المعرف: {person['المعرف']}\n"
        message += f"• الاسم: {person['الإسم']}\n"
        message += f"• الأب: {father_name} (المعرف: {person['معرف الأب']})\n"
        
        if pd.notna(person['المواليد']):
            message += f"• تاريخ الميلاد: {self.format_date(person['المواليد'])}\n"
            age = self.calculate_age(person['المواليد'], person['تاريخ الوفاة'])
            if age:
                message += f"• العمر: {age} سنة\n"
        
        if pd.notna(person['الحالة الإجتماعية']):
            message += f"• الحالة الاجتماعية: {person['الحالة الإجتماعية']}\n"
        
        if pd.notna(person['الوظيفة']):
            message += f"• الوظيفة: {person['الوظيفة']}\n"
        
        phone = self.format_phone_number(person['رقم الجوال'])
        if phone:
            message += f"• رقم الجوال: {phone}\n"
        
        message += "\nاختر ما تريد تعديله:"
        
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"edit_name_{person['المعرف']}")],
            [InlineKeyboardButton("👨 تغيير الأب", callback_data=f"edit_father_{person['المعرف']}")],
            [InlineKeyboardButton("📅 تاريخ الميلاد", callback_data=f"edit_birth_{person['المعرف']}")],
            [InlineKeyboardButton("💼 الوظيفة", callback_data=f"edit_job_{person['المعرف']}")],
            [InlineKeyboardButton("📞 رقم الجوال", callback_data=f"edit_phone_{person['المعرف']}")],
            [InlineKeyboardButton("✅ حفظ التعديلات", callback_data=f"save_edit_{person['المعرف']}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_edit_{person['المعرف']}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(message, reply_markup=reply_markup)

    async def select_father(self, query, person_id, father_id, context: CallbackContext):
        """تحديد الأب أثناء التعديل - الإصدار المحسن"""
        try:
            # حفظ التغيير المؤقت في context
            context.user_data['edit_changes']['معرف الأب'] = father_id
            father_name = self.get_father_name(father_id)
            
            # إنشاء لوحة مفاتيح واضحة للخطوات التالية
            keyboard = [
                [InlineKeyboardButton("✅ حفظ كل التعديلات", callback_data=f"save_edit_{person_id}")],
                [InlineKeyboardButton("↩️ العودة لقائمة التعديل", callback_data=f"edit_{person_id}")],
                [InlineKeyboardButton("❌ إلغاء كل التعديلات", callback_data=f"cancel_edit_{person_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ تم اختيار الأب الجديد مؤقتاً: **{father_name}** (المعرف: {father_id})\n\n"
                f"**مهم:** هذا التغيير لم يتم حفظه بعد.\n\n"
                f"اضغط على **'✅ حفظ كل التعديلات'** لتثبيت هذا التغيير وأي تعديلات أخرى، أو يمكنك العودة لتعديل بيانات أخرى.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في select_father: {e}")
            await query.edit_message_text(f"❌ حدث خطأ أثناء اختيار الأب: {str(e)}")


    async def save_edit_person(self, query, person_id, context: CallbackContext):
        """حفظ التعديلات"""
        try:
            if not context.user_data.get('edit_changes'):
                await query.edit_message_text("❌ لم تقم بأي تعديلات")
                return
            
            df = pd.read_excel(self.db_path)
            
            # التحقق من صحة معرف الأب إذا تم تغييره
            if 'معرف الأب' in context.user_data['edit_changes']:
                father_id = context.user_data['edit_changes']['معرف الأب']
                if father_id != 0:
                    father_exists = df[df['المعرف'] == father_id]
                    if father_exists.empty:
                        await query.edit_message_text(
                            f"❌ خطأ: معرف الأب {father_id} غير موجود في قاعدة البيانات",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("🔍 اختيار أب آخر", callback_data=f"edit_father_{person_id}")],
                                [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_edit_{person_id}")]
                            ])
                        )
                        return
            
            # تحديث الصف
            person_idx = df[df['المعرف'] == person_id].index[0]
            
            for field, new_value in context.user_data['edit_changes'].items():
                df.at[person_idx, field] = new_value
            
            # حفظ الملف
            df.to_excel(self.db_path, index=False)
            
            # تنظيف البيانات المؤقتة
            context.user_data.pop('editing_person', None)
            context.user_data.pop('edit_person_id', None)
            
            # رسالة النجاح
            changes_text = "\n".join([f"• {field}: {value}" for field, value in context.user_data['edit_changes'].items()])
            context.user_data.pop('edit_changes', None)
            
            message = f"✅ تم تحديث البيانات بنجاح\n\n"
            message += f"📊 التعديلات التي تمت:\n{changes_text}\n\n"
            message += f"🕒 تاريخ التحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            keyboard = [
                [InlineKeyboardButton("🔍 عرض التفاصيل", callback_data=f"view_{person_id}")],
                [InlineKeyboardButton("✏️ تعديل آخر", callback_data=f"edit_{person_id}")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"❌ خطأ في save_edit_person: {e}")
            await query.edit_message_text(f"❌ فشل في حفظ التعديلات: {str(e)}")

    async def cancel_edit_person(self, query, person_id, context: CallbackContext):
        """إلغاء التعديل"""
        context.user_data.pop('editing_person', None)
        context.user_data.pop('edit_person_id', None)
        context.user_data.pop('edit_changes', None)
        context.user_data.pop('editing_field', None)
        
        await query.edit_message_text(
            "❌ تم إلغاء التعديل",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 عرض التفاصيل", callback_data=f"view_{person_id}")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ])
        )


    async def handle_all_messages(self, update: Update, context: CallbackContext):
        """معالجة جميع الرسائل النصية وتوجيهها للدالة المناسبة"""
        user_id = update.effective_user.id
        user_message = update.message.text
        
        print(f"📨 رسالة مستلمة من {user_id}: {user_message}")
        
        # التحقق إذا كان المستخدم في وضع البحث عن صلة القرابة
        if context.user_data.get('relationship_search'):
            print("→ توجيه إلى handle_relationship_search")
            await self.handle_relationship_search(update, context)
            return
        
        # التحقق إذا كان المستخدم في وضع إضافة شخص
        if context.user_data.get('adding_person'):
            print("→ توجيه إلى handle_add_person_data")
            await self.handle_add_person_data(update, context)
            return
        
        # التحقق إذا كان المستخدم في وضع البحث
        if 'awaiting_search' in context.user_data:
            print("→ توجيه إلى handle_search_message")
            await self.handle_search_message(update, context)
            return
        
        # التحقق إذا كان المستخدم في وضع تعديل حقل
        if context.user_data.get('editing_field'):
            print("→ توجيه إلى handle_edit_field")
            await self.handle_edit_field(update, context)
            return
        
        # إذا لم تكن هناك حالة محددة
        await update.message.reply_text(
            "❌ لم أفهم طلبك. استخدم /start للبدء",
            reply_markup=self.create_error_keyboard()
        )
    
    async def handle_edit_field(self, update: Update, context: CallbackContext):
        """معالجة تعديل الحقول"""
        try:
            field = context.user_data['editing_field']
            person_id = context.user_data['edit_person_id']
            new_value = update.message.text
            
            # معالجة الحقول الخاصة
            if field == 'معرف الأب':
                if new_value == '0':
                    context.user_data['edit_changes']['معرف الأب'] = 0
                    await update.message.reply_text("✅ تم تعيين 'لا يوجد أب'")
                else:
                    # البحث عن الأب
                    await self.search_father_for_edit(update, new_value, context)
                    return
            else:
                # الحقول العادية
                context.user_data['edit_changes'][field] = new_value
                await update.message.reply_text(f"✅ تم تحديث {field} بنجاح")
            
            # العودة لواجهة التعديل
            df = pd.read_excel(self.db_path)
            person = df[df['المعرف'] == person_id].iloc[0]
            await self.show_edit_interface_from_message(update, person, context)
            
        except Exception as e:
            logging.error(f"❌ خطأ في handle_edit_field: {e}")
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
    
    async def search_father_for_edit(self, update: Update, search_term, context: CallbackContext):
        """البحث عن الأب أثناء التعديل"""
        try:
            df = pd.read_excel(self.db_path)
            
            # البحث عن مطابقات
            results = df[df['الإسم'].str.contains(search_term, na=False, case=False)]
            
            if results.empty:
                await update.message.reply_text("❌ لم يتم العثور على نتائج. حاول مرة أخرى:")
                return
            
            message = "🔍 نتائج البحث عن الأب:\n\n"
            keyboard = []
            
            for _, person in results.head(8).iterrows():
                father_name = self.get_father_name(person['معرف الأب'])
                message += f"• {person['الإسم']} بن {father_name} (المعرف: {person['المعرف']})\n"
                keyboard.append([InlineKeyboardButton(
                    f"{person['الإسم']} - {person['المعرف']}", 
                    callback_data=f"select_father_{context.user_data['edit_person_id']}_{person['المعرف']}"
                )])
            
            keyboard.append([InlineKeyboardButton("🔍 بحث جديد", callback_data=f"edit_father_{context.user_data['edit_person_id']}")])
            keyboard.append([InlineKeyboardButton("❌ لا يوجد أب", callback_data=f"select_father_{context.user_data['edit_person_id']}_0")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(message, reply_markup=reply_markup)
            
        except Exception as e:
            logging.error(f"❌ خطأ في search_father_for_edit: {e}")
            await update.message.reply_text(f"❌ حدث خطأ في البحث: {str(e)}")
    
    async def show_edit_interface_from_message(self, update: Update, person, context: CallbackContext):
        """عرض واجهة التعديل من رسالة"""
        father_name = self.get_father_name(person['معرف الأب'])
        
        message = f"✏️ تعديل بيانات {person['الإسم']} {father_name} شمّا\n\n"
        message += f"📋 البيانات الحالية:\n"
        message += f"• المعرف: {person['المعرف']}\n"
        message += f"• الاسم: {person['الإسم']}\n"
        message += f"• الأب: {father_name} (المعرف: {person['معرف الأب']})\n"
        
        if pd.notna(person['المواليد']):
            message += f"• تاريخ الميلاد: {self.format_date(person['المواليد'])}\n"
            age = self.calculate_age(person['المواليد'], person['تاريخ الوفاة'])
            if age:
                message += f"• العمر: {age} سنة\n"
        
        message += "\nاختر ما تريد تعديله:"
        
        keyboard = [
            [InlineKeyboardButton("✏️ تعديل الاسم", callback_data=f"edit_name_{person['المعرف']}")],
            [InlineKeyboardButton("👨 تغيير الأب", callback_data=f"edit_father_{person['المعرف']}")],
            [InlineKeyboardButton("📅 تاريخ الميلاد", callback_data=f"edit_birth_{person['المعرف']}")],
            [InlineKeyboardButton("💼 الوظيفة", callback_data=f"edit_job_{person['المعرف']}")],
            [InlineKeyboardButton("📞 رقم الجوال", callback_data=f"edit_phone_{person['المعرف']}")],
            [InlineKeyboardButton("✅ حفظ التعديلات", callback_data=f"save_edit_{person['المعرف']}")],
            [InlineKeyboardButton("❌ إلغاء", callback_data=f"cancel_edit_{person['المعرف']}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)

    async def show_person_details_message(self, update: Update, person):
        """عرض تفاصيل الشخص في رسالة"""
        try:
            # استخدام التقرير التفصيلي كافتراضي للرسائل المباشرة
            message = self.format_person_details(person)
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث جديد", callback_data="search_partial")],
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="show_stats")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            
            # إضافة زر التعديل إذا كانت هناك صلاحية
            if hasattr(update, 'effective_user') and self.check_permission(update.effective_user.id, 'edit_all'):
                keyboard.append([InlineKeyboardButton("✏️ تعديل البيانات", callback_data=f"edit_{person['المعرف']}")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_person_details_message: {e}")
            await update.message.reply_text(
                f"❌ خطأ في عرض التفاصيل: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )
    
    async def show_stats(self, query, context: CallbackContext):
        """عرض إحصائيات العائلة"""
        try:
            df = pd.read_excel(self.db_path)
            total_members = len(df)
            
            # إحصائيات إضافية
            generations = {}
            for _, person in df.iterrows():
                depth = self.calculate_generation_depth(person['المعرف'], df)
                generations[depth] = generations.get(depth, 0) + 1
            
            message = f"""
📊 *إحصائيات عائلة شما*

👥 *عدد الأفراد:* {total_members}

📈 *التوزيع العمري:*
"""
            for gen, count in sorted(generations.items()):
                message += f"• الجيل {gen}: {count} فرد\n"
            
            message += "\n💡 *استخدم خيار البحث للعثور على أشخاص محددين*"
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث عن شخص", callback_data="search_partial")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_stats: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ في الإحصائيات: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

    # ==================== نظام صلة القرابة ====================

    def find_common_ancestor(self, person1_id, person2_id):
        """إيجاد الجد المشترك وأقصر مسار للقرابة"""
        try:
            df = pd.read_excel(self.db_path)
            
            # الحصول على أسلاف الشخص الأول
            ancestors1 = self.get_ancestors(person1_id, df)
            # الحصول على أسلاف الشخص الثاني
            ancestors2 = self.get_ancestors(person2_id, df)
            
            # إيجاد الجد المشترك
            common_ancestors = []
            for anc1 in ancestors1:
                for anc2 in ancestors2:
                    if anc1['id'] == anc2['id']:
                        common_ancestors.append({
                            'ancestor': anc1,
                            'distance1': anc1['distance'],
                            'distance2': anc2['distance']
                        })
            
            if not common_ancestors:
                return None
            
            # اختيار أقرب جد مشترك
            closest_ancestor = min(common_ancestors, 
                                 key=lambda x: max(x['distance1'], x['distance2']))
            
            return closest_ancestor
            
        except Exception as e:
            logging.error(f"❌ خطأ في find_common_ancestor: {e}")
            return None

    def get_ancestors(self, person_id, df):
        """الحصول على جميع أسلاف الشخص"""
        ancestors = []
        current_id = person_id
        distance = 0
        
        while True:
            if current_id == 0 or pd.isna(current_id):
                break
                
            person = df[df['المعرف'] == current_id]
            if person.empty:
                break
                
            ancestors.append({
                'id': current_id,
                'name': str(person.iloc[0]['الإسم']),
                'distance': distance
            })
            
            father_id = person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                break
                
            current_id = father_id
            distance += 1
        
        return ancestors

    def get_relationship_type(self, distance1, distance2):
        """تحديد نوع صلة القرابة بناء على المسافة"""
        # إذا كان المسافات متساوية (أبناء عم)
        if distance1 == distance2:
            if distance1 == 1:
                return "أخوة"
            elif distance1 == 2:
                return "أبناء عم"
            elif distance1 == 3:
                return "أبناء عم من الدرجة الثانية"
            elif distance1 == 4:
                return "أبناء عم من الدرجة الثالثة"
            else:
                return f"أبناء عم من الدرجة {distance1 - 1}"
        
        # العلاقات العمودية (أب/ابن/جد/حفيد)
        if distance1 == 0:
            if distance2 == 1:
                return "الأب"
            elif distance2 == 2:
                return "الجد"
        elif distance2 == 0:
            if distance1 == 1:
                return "الابن"
            elif distance1 == 2:
                return "الحفيد"
        
        # العلاقات المختلطة
        if distance1 == 1 and distance2 == 2:
            return "العم"
        elif distance1 == 2 and distance2 == 1:
            return "ابن الأخ"
        
        return f"قريب (المسافة: {distance1},{distance2})"

    def build_relationship_tree(self, common_ancestor_id, person1_id, person2_id, df):
        """بناء شجرة العلاقة بين الشخصين"""
        try:
            # الحصول على خطوط النسب
            line1 = self.get_line_to_ancestor(person1_id, common_ancestor_id, df)
            line2 = self.get_line_to_ancestor(person2_id, common_ancestor_id, df)
            
            # بناء الشجرة
            tree_lines = []
            
            # إضافة الجد المشترك
            ancestor_info = df[df['المعرف'] == common_ancestor_id].iloc[0]
            ancestor_name = str(ancestor_info['الإسم'])
            tree_lines.append(f"    {ancestor_name} (المعرف: {common_ancestor_id})")
            
            # بناء الفروع
            branch1 = self.build_branch(line1, "    ├── ")
            branch2 = self.build_branch(line2, "    └── ")
            
            tree_lines.extend(branch1)
            tree_lines.extend(branch2)
            
            return "\n".join(tree_lines)
            
        except Exception as e:
            logging.error(f"❌ خطأ في build_relationship_tree: {e}")
            return "غير متوفر"

    def get_line_to_ancestor(self, person_id, ancestor_id, df):
        """الحصول على خط النسب من الشخص إلى الجد"""
        line = []
        current_id = person_id
        
        while current_id != ancestor_id:
            person = df[df['المعرف'] == current_id]
            if person.empty:
                break
                
            line.append({
                'id': current_id,
                'name': str(person.iloc[0]['الإسم'])
            })
            
            father_id = person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0 or father_id == ancestor_id:
                break
                
            current_id = father_id
        
        return line

    def build_branch(self, line, prefix):
        """بناء فرع من الشجرة"""
        if not line:
            return []
        
        branch_lines = []
        for i, person in enumerate(line):
            if i == len(line) - 1:
                branch_lines.append(f"{prefix} {person['name']} (المعرف: {person['id']})")
            else:
                branch_lines.append(f"{prefix} {person['name']}")
                prefix = prefix.replace("├──", "│   ").replace("└──", "    ")
        
        return branch_lines

    async def show_relationship(self, query, person1_id, person2_id, context: CallbackContext):
        """عرض صلة القرابة بين شخصين"""
        try:
            df = pd.read_excel(self.db_path)
            
            # الحصول على بيانات الشخصين
            person1 = df[df['المعرف'] == person1_id].iloc[0]
            person2 = df[df['المعرف'] == person2_id].iloc[0]
            
            person1_name = str(person1['الإسم'])
            person2_name = str(person2['الإسم'])
            
            # الحصول على أسماء الآباء للعرض
            person1_father = self.get_father_name(person1['معرف الأب'])
            person2_father = self.get_father_name(person2['معرف الأب'])
            
            # إيجاد الجد المشترك
            common_ancestor_info = self.find_common_ancestor(person1_id, person2_id)
            
            if not common_ancestor_info:
                message = f"🧬 **نتيجة معرفة صلة القرابة**\n\n"
                message += f"👤 **الأول:** {person1_name} {person1_father} (المعرف: {person1_id})\n"
                message += f"👤 **الثاني:** {person2_name} {person2_father} (المعرف: {person2_id})\n\n"
                message += "❌ **لا توجد صلة قرابة مباشرة بين الشخصين**\n\n"
                message += "💡 **ملاحظة:** قد يكونان من فروع مختلفة من العائلة"
                
                keyboard = [
                    [InlineKeyboardButton("🔍 بحث عن أشخاص", callback_data="search_partial")],
                    [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            # بناء رسالة النتيجة
            ancestor_id = common_ancestor_info['ancestor']['id']
            distance1 = common_ancestor_info['distance1']
            distance2 = common_ancestor_info['distance2']
            
            ancestor_data = df[df['المعرف'] == ancestor_id].iloc[0]
            ancestor_name = str(ancestor_data['الإسم'])
            
            relationship_type = self.get_relationship_type(distance1, distance2)
            
            # بناء شجرة العلاقة
            relationship_tree = self.build_relationship_tree(ancestor_id, person1_id, person2_id, df)
            
            # معلومات إضافية عن الجد المشترك
            ancestor_age = self.calculate_age(ancestor_data['المواليد'], ancestor_data['تاريخ الوفاة'])
            ancestor_status = "متوفى" if pd.notna(ancestor_data['تاريخ الوفاة']) else "على قيد الحياة"
            
            # عدد أبناء الجد المشترك
            children_count = len(df[df['معرف الأب'] == ancestor_id])
            
            message = f"🧬 **نتيجة معرفة صلة القرابة**\n\n"
            message += f"👤 **الأول:** {person1_name} {person1_father} (المعرف: {person1_id})\n"
            message += f"👤 **الثاني:** {person2_name} {person2_father} (المعرف: {person2_id})\n\n"
            message += f"📋 **صلة القرابة:**\n"
            message += f"• **العلاقة:** {relationship_type}\n"
            message += f"• **الجد المشترك:** {ancestor_name} (المعرف: {ancestor_id})\n\n"
            message += f"🌳 **شجرة العلاقة:**\n```\n{relationship_tree}\n```\n\n"
            message += f"💡 **معلومات إضافية:**\n"
            message += f"• عدد الأبناء المباشرين ل{ancestor_name}: {children_count} أبناء\n"
            message += f"• عمر الجد المشترك: {ancestor_age} سنة ({ancestor_status})\n"
            message += f"• المسافة من الجد المشترك: {distance1} أجيال للشخص الأول، {distance2} أجيال للشخص الثاني\n"
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث عن أشخاص", callback_data="search_partial")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_relationship: {e}")
            await query.edit_message_text(
                f"❌ حدث خطأ في حساب صلة القرابة: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

    async def start_relationship_search(self, query, context: CallbackContext):
        """بدء البحث عن صلة القرابة"""
        try:
            context.user_data['relationship_search'] = True
            context.user_data['relationship_step'] = 'first_person'
            context.user_data['relationship_data'] = {}
            
            await query.edit_message_text(
                "🧬 **بحث عن صلة القرابة**\n\n"
                "أدخل معرف أو اسم الشخص الأول:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔍 بحث بالاسم", callback_data="search_relationship_first")],
                    [InlineKeyboardButton("↩️ إلغاء", callback_data="back_to_main")]
                ])
            )
            
        except Exception as e:
            logging.error(f"❌ خطأ في start_relationship_search: {e}")
            await query.edit_message_text(f"❌ حدث خطأ: {str(e)}")

    async def handle_relationship_search(self, update: Update, context: CallbackContext):
        """معالجة البحث عن صلة القرابة"""
        try:
            if not context.user_data.get('relationship_search'):
                return
                
            user_input = update.message.text
            current_step = context.user_data.get('relationship_step')
            
            df = pd.read_excel(self.db_path)
            
            if current_step == 'first_person':
                # البحث عن الشخص الأول
                results = self.search_person(user_input, df)
                if len(results) == 1:
                    context.user_data['relationship_data']['person1'] = results.iloc[0]['المعرف']
                    context.user_data['relationship_step'] = 'second_person'
                    await update.message.reply_text(
                        f"✅ تم اختيار الشخص الأول: {results.iloc[0]['الإسم']} (المعرف: {results.iloc[0]['المعرف']})\n\n"
                        f"أدخل معرف أو اسم الشخص الثاني:"
                    )
                elif len(results) > 1:
                    await self.show_relationship_search_results(update, results, 'first', context)
                else:
                    await update.message.reply_text("❌ لم يتم العثور على الشخص. حاول مرة أخرى:")
                    
            elif current_step == 'second_person':
                # البحث عن الشخص الثاني
                results = self.search_person(user_input, df)
                if len(results) == 1:
                    context.user_data['relationship_data']['person2'] = results.iloc[0]['المعرف']
                    person1_id = context.user_data['relationship_data']['person1']
                    person2_id = results.iloc[0]['المعرف']
                    
                    # تنظيف البيانات المؤقتة
                    context.user_data.pop('relationship_search', None)
                    context.user_data.pop('relationship_step', None)
                    
                    # عرض نتيجة صلة القرابة
                    await self.show_relationship_from_message(update, person1_id, person2_id, context)
                    
                elif len(results) > 1:
                    await self.show_relationship_search_results(update, results, 'second', context)
                else:
                    await update.message.reply_text("❌ لم يتم العثور على الشخص. حاول مرة أخرى:")
                    
        except Exception as e:
            logging.error(f"❌ خطأ في handle_relationship_search: {e}")
            await update.message.reply_text(f"❌ حدث خطأ: {str(e)}")

    def search_person(self, search_term, df):
        """بحث عن شخص بالاسم أو المعرف"""
        try:
            # إذا كان المدخل رقم، البحث بالمعرف
            if search_term.isdigit():
                results = df[df['المعرف'] == int(search_term)]
                if not results.empty:
                    return results
            
            # البحث بالاسم
            results = df[df['الإسم'].str.contains(search_term, na=False, case=False)]
            return results
            
        except Exception as e:
            logging.error(f"❌ خطأ في search_person: {e}")
            return pd.DataFrame()

    async def show_relationship_search_results(self, update, results, step, context):
        """عرض نتائج البحث لصلة القرابة"""
        message = f"🔍 وجدت {len(results)} نتيجة:\n\n"
        keyboard = []
        
        for _, person in results.head(20).iterrows():
            name = str(person['الإسم'])
            person_id = str(person['المعرف'])
            father_name = self.get_father_name(person['معرف الأب'])
            
            message += f"• {name} بن {father_name} (المعرف: {person_id})\n"
            keyboard.append([InlineKeyboardButton(
                f"{name} - {person_id}",
                callback_data=f"rel_{step}_{person_id}"
            )])
        
        keyboard.append([InlineKeyboardButton("↩️ بحث جديد", callback_data="relationship_search")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(message, reply_markup=reply_markup)

    async def show_relationship_from_message(self, update, person1_id, person2_id, context):
        """عرض صلة القرابة من رسالة"""
        try:
            df = pd.read_excel(self.db_path)
            
            person1 = df[df['المعرف'] == person1_id].iloc[0]
            person2 = df[df['المعرف'] == person2_id].iloc[0]
            
            person1_name = str(person1['الإسم'])
            person2_name = str(person2['الإسم'])
            
            # الحصول على أسماء الآباء للعرض
            person1_father = self.get_father_name(person1['معرف الأب'])
            person2_father = self.get_father_name(person2['معرف الأب'])
            
            # إيجاد الجد المشترك
            common_ancestor_info = self.find_common_ancestor(person1_id, person2_id)
            
            if not common_ancestor_info:
                message = f"🧬 **نتيجة معرفة صلة القرابة**\n\n"
                message += f"👤 **الأول:** {person1_name} {person1_father} (المعرف: {person1_id})\n"
                message += f"👤 **الثاني:** {person2_name} {person2_father} (المعرف: {person2_id})\n\n"
                message += "❌ **لا توجد صلة قرابة مباشرة بين الشخصين**"
                
                keyboard = [
                    [InlineKeyboardButton("🔍 بحث عن أشخاص", callback_data="search_partial")],
                    [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            # بناء الرسالة
            ancestor_id = common_ancestor_info['ancestor']['id']
            distance1 = common_ancestor_info['distance1']
            distance2 = common_ancestor_info['distance2']
            
            ancestor_data = df[df['المعرف'] == ancestor_id].iloc[0]
            ancestor_name = str(ancestor_data['الإسم'])
            
            relationship_type = self.get_relationship_type(distance1, distance2)
            relationship_tree = self.build_relationship_tree(ancestor_id, person1_id, person2_id, df)
            
            ancestor_age = self.calculate_age(ancestor_data['المواليد'], ancestor_data['تاريخ الوفاة'])
            ancestor_status = "متوفى" if pd.notna(ancestor_data['تاريخ الوفاة']) else "على قيد الحياة"
            children_count = len(df[df['معرف الأب'] == ancestor_id])
            
            message = f"🧬 **نتيجة معرفة صلة القرابة**\n\n"
            message += f"👤 **الأول:** {person1_name} {person1_father} (المعرف: {person1_id})\n"
            message += f"👤 **الثاني:** {person2_name} {person2_father} (المعرف: {person2_id})\n\n"
            message += f"📋 **صلة القرابة:**\n"
            message += f"• **العلاقة:** {relationship_type}\n"
            message += f"• **الجد المشترك:** {ancestor_name} (المعرف: {ancestor_id})\n\n"
            message += f"🌳 **شجرة العلاقة:**\n```\n{relationship_tree}\n```\n\n"
            message += f"💡 **معلومات إضافية:**\n"
            message += f"• عدد الأبناء المباشرين ل{ancestor_name}: {children_count} أبناء\n"
            message += f"• عمر الجد المشترك: {ancestor_age} سنة ({ancestor_status})\n"
            message += f"• المسافة من الجد المشترك: {distance1} أجيال للشخص الأول، {distance2} أجيال للشخص الثاني\n"
            
            keyboard = [
                [InlineKeyboardButton("🔍 بحث عن أشخاص", callback_data="search_partial")],
                [InlineKeyboardButton("🏠 الرئيسية", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logging.error(f"❌ خطأ في show_relationship_from_message: {e}")
            await update.message.reply_text(
                f"❌ حدث خطأ في حساب صلة القرابة: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

    def get_person_name(self, person_id):
        """الحصول على اسم الشخص من المعرف"""
        try:
            df = pd.read_excel(self.db_path)
            person = df[df['المعرف'] == person_id]
            if not person.empty:
                return str(person.iloc[0]['الإسم'])
            return ""
        except:
            return ""

    def calculate_generation_depth(self, person_id, df):
        """حساب عمق الجيل للشخص"""
        depth = 1
        current_id = person_id
        
        while True:
            person = df[df['المعرف'] == current_id]
            if person.empty:
                break
                
            father_id = person.iloc[0]['معرف الأب']
            if pd.isna(father_id) or father_id == 0:
                break
                
            depth += 1
            current_id = father_id
        
        return depth

    async def handle_callback(self, update: Update, context: CallbackContext):
        """معالجة الضغط على الأزرار مع تنظيف تلقائي للبيانات"""
        query = update.callback_query
        await query.answer()

        # تنظيف استباقي للبيانات التالفة
        if 'add_step' in context.user_data and context.user_data.get('add_step') == 'search_father':
            # إذا كانت هناك عملية إضافة معلقة، تنظيفها
            context.user_data.clear()

        data = query.data
        user_id = query.from_user.id

        try:
            logging.info(f"📨 معالجة callback: {data} من المستخدم {user_id}")

            if data == "search_person":
                await self.ask_search_name(query, context)
            elif data == "search_partial":
                await self.ask_search_term(query, "partial", context)
            elif data == "search_brief":  # إضافة البحث المختصر
                await self.ask_search_term(query, "brief", context)       
            elif data == "show_stats":
                await self.show_stats(query, context)
            elif data == "relationship_search":
                await self.start_relationship_search(query, context)
            elif data == "back_to_main":
                await self.start_from_callback(query, context)
            elif data == "add_person":
                if self.check_permission(user_id, 'add'):
                    await self.start_add_person(query, context)
                else:
                    await query.edit_message_text("❌ ليس لديك صلاحية لإضافة أشخاص جدد")

            # معالجة البيانات التي تحتوي على أرقام - مع التحقق من الصحة
            elif data.startswith("view_"):
                try:
                    person_id = int(data.split("_")[1])
                    await self.show_person_details(query, person_id, context)
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف شخص غير صالح")

            elif data.startswith("search_"):
                search_type = data.split("_")[1]
                await self.ask_search_term(query, search_type, context)

            elif data == "save_person":
                await self.save_new_person(query, context)

            elif data == "cancel_add":
                await self.cancel_add_person(query, context)

            # معالجة التعديلات بشكل صحيح
            elif data.startswith("edit_"):
                try:
                    # استخراج معرف الشخص من نهاية البيانات
                    parts = data.split('_')
                    if len(parts) >= 2 and parts[-1].isdigit():
                        person_id = int(parts[-1])

                        # تحديد نوع التعديل
                        if "name" in data:
                            await self.start_edit_field(query, person_id, "الإسم", context)
                        elif "father" in data:
                            await self.start_edit_father(query, person_id, context)
                        elif "birth" in data:
                            await self.start_edit_field(query, person_id, "المواليد", context)
                        elif "job" in data:
                            await self.start_edit_field(query, person_id, "الوظيفة", context)
                        elif "phone" in data:
                            await self.start_edit_field(query, person_id, "رقم الجوال", context)
                        else:
                            await self.start_edit_person(query, person_id, context)
                    else:
                        await query.edit_message_text("❌ معرف شخص غير صالح للتعديل")
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف شخص غير صالح للتعديل")

            elif data.startswith("select_father_"):
                try:
                    parts = data.split("_")
                    if len(parts) >= 4:
                        person_id = int(parts[2])
                        father_id = int(parts[3])
                        await self.select_father(query, person_id, father_id, context)
                    else:
                        await query.edit_message_text("❌ بيانات غير صالحة")
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف غير صالح")

            elif data.startswith("save_edit_"):
                try:
                    person_id = int(data.split("_")[2])
                    await self.save_edit_person(query, person_id, context)
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف شخص غير صالح")

            elif data.startswith("cancel_edit_"):
                try:
                    person_id = int(data.split("_")[2])
                    await self.cancel_edit_person(query, person_id, context)
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف شخص غير صالح")

            # معالجة الحالات الخاصة للإضافة
            elif data.startswith("select_father_add_"):
                try:
                    father_id = int(data.split("_")[3])
                    await self.handle_father_selection(query, father_id, context)
                except (ValueError, IndexError):
                    await query.edit_message_text("❌ معرف الأب غير صالح")

            elif data == "search_again_father":
                await query.edit_message_text("🔍 ابحث عن الأب (أدخل جزء من الاسم أو '0' إذا لم يكن معروفاً):")

            elif data == "no_father":
                context.user_data['new_person']['معرف الأب'] = 0
                context.user_data['add_step'] = 'birth_date'
                await query.edit_message_text("✅ تم تعيين 'لا يوجد أب'\n\nأدخل تاريخ الميلاد (YYYY-MM-DD، أو اكتب 'تخطي'):")

            # معالجة صلة القرابة
            elif data.startswith("rel_"):
                parts = data.split("_")
                if len(parts) >= 3:
                    step = parts[1]
                    person_id = int(parts[2])

                    if step == 'first':
                        context.user_data['relationship_data']['person1'] = person_id
                        context.user_data['relationship_step'] = 'second_person'
                        person_name = self.get_person_name(person_id)
                        await query.edit_message_text(
                            f"✅ تم اختيار الشخص الأول: {person_name} (المعرف: {person_id})\n\n"
                            f"أدخل معرف أو اسم الشخص الثاني:"
                        )
                    elif step == 'second':
                        context.user_data['relationship_data']['person2'] = person_id
                        person1_id = context.user_data['relationship_data']['person1']

                        # تنظيف البيانات المؤقتة
                        context.user_data.pop('relationship_search', None)
                        context.user_data.pop('relationship_step', None)

                        # عرض النتيجة
                        await self.show_relationship(query, person1_id, person_id, context)

            else:
                await query.edit_message_text(
                    "❌ أمر غير معروف",
                    reply_markup=self.create_error_keyboard()
                )

        except Exception as e:
            logging.error(f"❌ خطأ في handle_callback: {e}")
            # تنظيف كامل للبيانات
            context.user_data.clear()
            await query.edit_message_text(
                "🔄 تم إعادة تعيين النظام. يمكنك المحاولة مرة أخرى.",
                reply_markup=self.create_main_keyboard(user_id)
            )
    async def reset_bot_state(self, update: Update, context: CallbackContext):
        """إعادة تعيين البوت يدوياً - حل سريع للمشاكل"""
        # تنظيف كامل لبيانات المستخدم
        context.user_data.clear()

        await update.message.reply_text(
            "🔄 **تم إعادة تعيين البوت بنجاح**\n\n"
            "تم تنظيف جميع البيانات المؤقتة وإعادة البوت للحالة الطبيعية.\n"
            "يمكنك الآن استخدام جميع الميزات بدون مشاكل.",
            reply_markup=self.create_main_keyboard(update.effective_user.id)
        )
        print(f"✅ تم إعادة تعيين البوت يدوياً للمستخدم {update.effective_user.id}")


async def handle_father_selection_callback(self, query, father_id, context: CallbackContext):
    """معالجة اختيار الأب أثناء التعديل - الإصدار المحسن"""
    try:
        print(f"🔍 معالجة اختيار الأب للتعديل: {father_id}")
        
        # الحصول على معرف الشخص الذي يتم تعديله
        person_id = context.user_data.get('edit_person_id')
        if not person_id:
            await query.edit_message_text(
                "❌ لم يتم العثور على بيانات التعديل",
                reply_markup=self.create_error_keyboard()
            )
            return
        
        # التحقق من أن father_id رقم صالح
        if not isinstance(father_id, int):
            try:
                father_id = int(father_id)
            except (ValueError, TypeError):
                await query.edit_message_text(
                    f"❌ معرف الأب غير صالح: {father_id}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("↩️ العودة للتعديل", callback_data=f"edit_{person_id}")]
                    ])
                )
                return
        
        if father_id < 0:
            await query.edit_message_text(
                f"❌ معرف الأب غير صالح: {father_id}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("↩️ العودة للتعديل", callback_data=f"edit_{person_id}")]
                ])
            )
            return
        
        # إذا كان الأب = 0 (لا يوجد أب)
        if father_id == 0:
            context.user_data['edit_changes']['معرف الأب'] = 0
            father_name = "لا يوجد"
        else:
            # التحقق من وجود الأب في قاعدة البيانات
            df = pd.read_excel(self.db_path)
            father_exists = df[df['المعرف'] == father_id]
            
            if father_exists.empty:
                await query.edit_message_text(
                    f"❌ معرف الأب {father_id} غير موجود في قاعدة البيانات",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔍 بحث جديد", callback_data=f"edit_father_{person_id}")],
                        [InlineKeyboardButton("❌ لا يوجد أب", callback_data=f"select_father_{person_id}_0")]
                    ])
                )
                return
            
            # حفظ الأب الجديد
            context.user_data['edit_changes']['معرف الأب'] = father_id
            father_name = self.get_father_name(father_id)
        
        # تأكيد الحفظ في context
        context.user_data['edit_changes']['معرف الأب'] = father_id
        
        # عرض رسالة النجاح والعودة لواجهة التعديل
        keyboard = [
            [InlineKeyboardButton("✅ حفظ التعديلات", callback_data=f"save_edit_{person_id}")],
            [InlineKeyboardButton("↩️ العودة للتعديل", callback_data=f"edit_{person_id}")],
            [InlineKeyboardButton("❌ إلغاء التعديل", callback_data=f"cancel_edit_{person_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ تم اختيار الأب الجديد: {father_name} (المعرف: {father_id})\n\n"
            f"يمكنك:\n"
            f"• الاستمرار في التعديل\n"
            f"• حفظ التعديلات\n"
            f"• العودة لواجهة التعديل الرئيسية",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logging.error(f"❌ خطأ في handle_father_selection_callback: {e}")
        
        person_id = context.user_data.get('edit_person_id')
        if person_id:
            keyboard = [
                [InlineKeyboardButton("↩️ العودة للتعديل", callback_data=f"edit_{person_id}")],
                [InlineKeyboardButton("❌ إلغاء التعديل", callback_data=f"cancel_edit_{person_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"❌ حدث خطأ في اختيار الأب: {str(e)}\n\n"
                f"يرجى المحاولة مرة أخرى",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text(
                f"❌ حدث خطأ في اختيار الأب: {str(e)}",
                reply_markup=self.create_error_keyboard()
            )

def main():
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ لم يتم تعيين BOT_TOKEN")
        return
    
    try:
        print("🚀 بدء تشغيل بوت عائلة شما المحسن...")
        
        bot = FamilyBot()
        application = Application.builder().token(BOT_TOKEN).build()
        
        # إضافة المعالجات - الترتيب مهم!
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CallbackQueryHandler(bot.handle_callback))
        application.add_handler(CommandHandler("reset", bot.reset_bot_state))
        
        # معالج الرسائل العام - يجب أن يكون الأخير
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            bot.handle_all_messages
        ))
        
        print("🤖 بوت عائلة شما المحسن يعمل الآن...")
        application.run_polling()
        
    except Exception as e:
        print(f"❌ فشل تشغيل البوت: {e}")

if __name__ == '__main__':
    main()