import frappe
from frappe.auth import LoginManager
from frappe.utils import cstr,today,cint
from bs4 import BeautifulSoup
import random

def gen_response(status, message, data=[]):
	frappe.response['http_status_code'] = status
	if status == 500:
		frappe.response['message'] = BeautifulSoup(str(message)).get_text()
	else:
		frappe.response['message'] = message
	frappe.response['data'] = data
	frappe.clear_messages()

@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
	try:
		login_manager = LoginManager()
		login_manager.authenticate(usr, pwd)
		login_manager.post_login()
		if frappe.response['message'] == 'Logged In':
			frappe.response['user'] = login_manager.user
			frappe.response['key_details'] = generate_key(login_manager.user)
		gen_response(200, frappe.response['message'])
	except frappe.AuthenticationError:
		gen_response(500, frappe.response['message'])
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))


def generate_key(user):
	user_details = frappe.get_doc("User", user)
	api_secret = api_key = ''
	if not user_details.api_key and not user_details.api_secret:
		api_secret = frappe.generate_hash(length=15)
		# if api key is not set generate api key
		api_key = frappe.generate_hash(length=15)
		user_details.api_key = api_key
		user_details.api_secret = api_secret
		user_details.save(ignore_permissions=True)
	else:
		api_secret = user_details.get_password('api_secret')
		api_key = user_details.get('api_key')
	return {"api_secret": api_secret, "api_key": api_key}


@frappe.whitelist()
def add_intake_form(**kwargs):
	try:
		data = frappe._dict(kwargs)
		intake_form_doc = frappe.get_doc(dict(
			doctype = "Intake Form",
			user = frappe.session.user,
			first_name = data.get('first_name'),
			title = data.get('title'),
			prefix = data.get('prefix'),
			street = data.get('street'),
			street2 = data.get('street2'),
			city = data.get('city'),
			state = data.get('state'),
			postal_code = data.get('postal_code'),
			country = data.get('country'),
			phone = data.get('phone'),
			email = data.get('email')
		)).insert(ignore_permissions = True)
		gen_response(200,"Intake Form Inserted Successfully")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))

@frappe.whitelist()
def get_cert_settings():
	try:
		cert_settings = frappe.get_doc("Cert Settings","Cert Settings")
		cert_settings = {
			"intake_form": True if frappe.db.exists("Intake Form",{"user":frappe.session.user}) else False,
			"version_details": dict(
				version = cert_settings.get("version"),
				update_message = cert_settings.get("update_message"),
				force = cert_settings.get("force")
			)
		}
		gen_response(200,"App Settings Get Successfully",cert_settings)
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))


@frappe.whitelist()
def create_account(**kwargs):
	try:
		data = frappe._dict(kwargs)
		if frappe.db.exists("User",data.get("email")):
			return gen_response(200,"User Already Exists With Same Email")
		user = create_user(data)
		create_patient(data,user)
		create_student(data,user)
		gen_response(200,"User Created Successfully")
	except frappe.DoesNotExistError:
		frappe.clear_messages()
		gen_response(200,"User Created Successfully")
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))

def create_user(data):
	from frappe.utils.password import update_password as _update_password

	employee_name = data.get("username").split(" ")
	middle_name = last_name = ""

	if len(employee_name) >= 3:
		last_name = " ".join(employee_name[2:])
		middle_name = employee_name[1]
	elif len(employee_name) == 2:
		last_name = employee_name[1]

	first_name = employee_name[0]
	user = frappe.new_doc("User")
	user_doc = frappe.get_doc(dict(
		doctype = "User",
		email = data.get("email"),
		enabled = 1,
		first_name = first_name,
		middle_name = middle_name,
		last_name = last_name,
		send_welcome_email = 0
	))
	user_doc.append_roles("Cert Mobile App")
	res = user_doc.insert(ignore_permissions = True)
	_update_password(res.name,pwd=data.get("password"))
	return user_doc.name

def create_patient(data,user):
	employee_name = data.get("username").split(" ")
	first_name = middle_name = last_name = ""
	first_name = employee_name[0]
	if len(employee_name) >= 3:
		last_name = " ".join(employee_name[2:])
		middle_name = employee_name[1]
	elif len(employee_name) == 2:
		last_name = employee_name[1]
	doc = frappe.get_doc(dict(
		doctype = "Patient",
		first_name = first_name,
		sex = "Male",
		email = data.get("email"),
		user_id = user,
		invite_user = 0
	)).insert(ignore_permissions = True)

def create_student(data,user):
	employee_name = data.get("username").split(" ")
	first_name = middle_name = last_name = ""
	first_name = employee_name[0]
	if len(employee_name) >= 3:
		last_name = " ".join(employee_name[2:])
		middle_name = employee_name[1]
	elif len(employee_name) == 2:
		last_name = employee_name[1]
	doc = frappe.get_doc(dict(
		doctype = "Student",
		first_name = first_name,
		last_name = last_name,
		middle_name = middle_name,
		student_email_id = data.get("email"),
		user_id = user
	)).insert(ignore_permissions = True)


@frappe.whitelist()
def get_profile_details():
	try:
		user_doc = frappe.get_doc("User",frappe.session.user)
		profile_details = dict(
			username = user_doc.full_name or "",
			email = user_doc.name,
			mobile_no = user_doc.mobile_no or "",
			language = user_doc.language,
			user_profile = user_doc.user_image or ""
		)
		gen_response(200, "User Profile Get Successfully", profile_details)
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))



def delete_old_file(doctype,docname,fieldname):
	files = frappe.get_all("File",filters={"attached_to_doctype":doctype,"attached_to_name":docname,"attached_to_field":fieldname},fields=["name"])
	for file in files:
		frappe.delete_doc("File",file.name,force=True)

@frappe.whitelist()
def update_profile_picture(profile_content,filename):
	try:
		import base64
		delete_old_file('User',frappe.session.user,"user_image")

		ret = frappe.get_doc({
			"doctype": "File",
			"attached_to_name": frappe.session.user,
			"attached_to_doctype": "User",
			"attached_to_field": "user_image",
			"file_name": filename,
			"is_private": 0,
			"content": profile_content,
			"decode": True
		})
		ret.save()
		frappe.db.commit()
		frappe.db.set_value("User",frappe.session.user,"user_image",ret.file_url)
		gen_response(200, "User Profile Updated")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))


@frappe.whitelist(allow_guest = True)
def forgot_password(email):
	try:
		if not frappe.db.exists("User",email):
			return gen_response(500,"No Any User Exists With Entered Email Address")	
		if send_otp(email):
			return gen_response(200,"OTP Sent Successfully")
		else:
			return gen_response(500,"Something Wrong In Sending OTP")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500, cstr(e))

@frappe.whitelist()
def id_generator_otp():
	return ''.join(random.choice('0123456789') for _ in range(6))

def send_otp(email):
	try:
		otpobj = frappe.db.get("Cert OTP", {"user": email})
		if otpobj:
			frappe.db.sql("""delete from `tabCert OTP` where user='""" + email + """'""")
		OPTCODE = id_generator_otp()
		mess = f"{OPTCODE} is OTP for your cert app."
		userOTP = frappe.get_doc(dict(
			doctype="Cert OTP",
			user=email,
			otp=OPTCODE
		)).insert(ignore_permissions=True)
		return True
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		return False

@frappe.whitelist(allow_guest=True)
def verify_otp_code(email, otp):
	try:
		otpobj = frappe.db.get("Cert OTP", {"user": email})
		if cstr(otpobj.otp) == cstr(otp):
			data = generate_key(email)
			return gen_response(200,"OTP Successfully Verified",data)
		else:
			return gen_response(417,"Invalid OTP")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500,cstr(e))

@frappe.whitelist()
def reset_password(password,confirm_password):
	from frappe.utils.password import update_password
	if not cstr(password) == cstr(confirm_password):
		return gen_response(417,"Password And Confirm Password Not Same")
	try:
		update_password(frappe.session.user, password)
		gen_response(200,"Password changed Successfully")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500,cstr(e))

@frappe.whitelist()
def get_activity_details(date=None):
	try:
		if not date:
			date = today()
		activity_details = []

		for row in frappe.get_all("Cert Activity",filters={"enable":1},fields=["name"]):
			value = 0
			if frappe.db.exists("Cert Day Activity Log",row.name+"-"+cstr(date)+"-"+frappe.session.user):
				value = frappe.db.get_value("Cert Day Activity Log",row.name+"-"+cstr(date)+"-"+frappe.session.user,"details")
			activity_details.append(dict(
				activity = row.name,
				value = cint(value)
			))
		gen_response(200,"Activity Details Get Successfully",activity_details)
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500,cstr(e))

@frappe.whitelist()
def update_activity_details(date=None,activity_type=None,details=None):
	try:
		if not date or not activity_type or not details:
			return gen_response(500,"Missing param for call this api")
		if frappe.db.exists("Cert Day Activity Log",activity_type+"-"+cstr(date)+"-"+frappe.session.user):
			frappe.db.set_value("Cert Day Activity Log",activity_type+"-"+cstr(date)+"-"+frappe.session.user,"details",details)
		else:
			doc = frappe.get_doc(dict(
				doctype = "Cert Day Activity Log",
				cert_activity = activity_type,
				user = frappe.session.user,
				date = date,
				details = details
			)).insert(ignore_permissions=True)
		return gen_response(200,"Cert Day Activity Updated")
	except Exception as e:
		frappe.log_error(frappe.get_traceback())
		gen_response(500,cstr(e))
