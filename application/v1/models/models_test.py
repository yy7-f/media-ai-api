# from flask import Flask
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Float, create_engine
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy import desc
from sqlalchemy.ext.hybrid import hybrid_property
from datetime import datetime, UTC
import pandas as pd
import numpy as np
from application import db


# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:Nishi8@localhost/invoices_test'
# # Replace 'username', 'password', 'localhost', and 'db_name' with your actual PostgreSQL credentials and database name
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Suppresses SQLAlchemy warning
# db = SQLAlchemy(app)
#
# DATABASE_URL = 'postgresql://localhost/invoices_test'
#
# # Create an engine and session
# engine = create_engine(DATABASE_URL)
# Session = sessionmaker(bind=engine)
# session = Session()


############################################################################################################
# add data from csv file
############################################################################################################

# # File path to the CSV file
# csv_file = 'csv/供給地点一覧（プラン名追加）-Table 1.csv'
# # Read the CSV file into a pandas DataFrame
# df = pd.read_csv(csv_file)
# # print(df.head())
# # Specify the table name in the database
# table_name = 'invoices_test'
# # Insert data from DataFrame into PostgreSQL table
# df.to_sql(table_name, engine, if_exists='append', index=False)
# print(f"Values added to the '{table_name}' table in PostgreSQL.")

############################################################################################################


# Define your model
class PaymentMethod(db.Model):
    __tablename__ = 'payment_method'
    id = Column(Integer, primary_key=True)
    payment_method = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class Customers(db.Model):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    payment_method_id = Column(Integer, ForeignKey('payment_method.id'))
    customer_number = Column(String(20), unique=True, nullable=False)
    customer_name = Column(String(200), nullable=False)
    _payment_date = Column(Date, name="payment_date")
    address = Column(String(200))
    invoice_name = Column(String(200), nullable=False)
    invoice_address = Column(String(200), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))

    @hybrid_property
    def payment_date(self) -> str:
        return self._payment_date.strftime('%Y-%m-%d')


class Region(db.Model):
    __tablename__ = 'region'
    id = Column(Integer, primary_key=True)
    region_name_en = Column(String(120), nullable=False)
    region_name_jp = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))

############################################################################################################
# add data to the region table
############################################################################################################


# region_to_add = [
#     Region(region_name_en='Kanto', region_name_jp='関東'),
#     Region(region_name_en='Kansai', region_name_jp='関西'),
# ]
# session.add_all(region_to_add)
# # Commit the session to persist the changes to the database
# session.commit()
# # Close the session
# session.close()

############################################################################################################


class SupplyPoints(db.Model):
    __tablename__ = 'supply_points'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'))
    region_id = Column(Integer, ForeignKey('region.id'))
    spid = Column(String(22), unique=True, nullable=False)
    supply_point_name = Column(String(200), nullable=False)
    supply_point_address = Column(String(200), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))
    monthly_usage = relationship('MonthlyUsage', backref='supply_points')

    def latest_monthly_usage(self):
        return MonthlyUsage.query.filter_by(MonthlyUsage.supply_point_id == self.id).order_by(desc(MonthlyUsage.month)).first()


class BasicChargeType(db.Model):
    __tablename__ = 'basic_charge_type'
    id = Column(Integer, primary_key=True)
    basic_charge_type = Column(String(120), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class Contracts(db.Model):
    __tablename__ = 'contracts'
    id = Column(Integer, primary_key=True)
    supply_point_id = Column(Integer, ForeignKey('supply_points.id'))
    plan_id = Column(Integer, ForeignKey('plan.id'))
    basic_charge_type_id = Column(Integer, ForeignKey('basic_charge_type.id'))
    energy_charge_summer = Column(Integer, nullable=False)
    energy_charge_winter = Column(Integer, nullable=False)
    energy_charge_non_summer = Column(Integer, nullable=False)
    energy_charge_non_winter = Column(Integer, nullable=False)
    contracted_supply_capacity_actual = Column(Integer)
    contracted_supply_capacity_negotiable = Column(Integer)
    power_factor_discount = Column(Integer, nullable=False)
    reverse_supply = Column(Integer)
    reverse_line = Column(Integer)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class Plan(db.Model):
    __tablename__ = 'plan'
    id = Column(Integer, primary_key=True)
    plan_name = Column(String(120), nullable=False)
    plan_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class MonthlyUsage(db.Model):
    __tablename__ = 'monthly_usage'
    id = Column(Integer, primary_key=True)
    supply_point_id = Column(Integer, ForeignKey('supply_points.id'))
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    usage = Column(Integer, nullable=False)
    startdate = Column(Date, nullable=False)
    enddate = Column(Date, nullable=False)
    power_factor = Column(Integer, nullable=False)
    inspection_date = Column(Date, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))
    thirty_min_usage = relationship('ThirtyMinUsage', backref='monthly_usage')
    # invoice = relationship('Invoice', backref='monthly_usage')

    def usage_summer(self):
        if not self.thirty_min_usage:
            return None
        return sum([usage.usage for usage in self.thirty_min_usage if usage.month in [7, 8, 9]])

    def usage_winter(self):
        if not self.thirty_min_usage:
            return None
        return sum([usage.usage for usage in self.thirty_min_usage if usage.month in [12, 1, 2]])

    def peak_demand_last_year(self):
        peak_demand = PeakDemand.query.filter_by(id).first(PeakDemand.supply_point_id == self.supply_point_id,
                                                           PeakDemand.month_number <= self.month,
                                                           PeakDemand.month_number >= self.month - 12).order_by(desc(PeakDemand.month_number)).all()
        return peak_demand

    def peak_usage_year(self):
        peak_demands = self.peak_demand_last_year()
        if len(peak_demands) == 12:
            peak_demand = np.array([peak_demand.peak_demand for peak_demand in peak_demands]).max()
            return peak_demand
        else:
            return None

    def invoice_month(self):
        return f"{str(self.year)}年{str(self.month)}月"

    def invoice_duration(self):
        return f"{datetime.strptime(str(self.startdate), '%Y-%m-%d').strftime('%Y年%m月%d日')} ～ {datetime.strptime(str(self.enddate), '%Y-%m-%d').strftime('%Y年%m月%d日')}"
    def inspection_date(self):
        return f"{datetime.strptime(str(self.inspection_date), '%Y-%m-%d').strftime('%Y年%m月%d日')}"


class ThirtyMinUsage(db.Model):
    __tablename__ = 'thirty_min_usage'
    id = Column(Integer, primary_key=True)
    monthly_usage_id = Column(Integer, ForeignKey('monthly_usage.id'))
    date = Column(Integer, nullable=False)
    usage = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class Invoice(db.Model):
    __tablename__ = 'invoice'
    id = Column(Integer, primary_key=True)
    supply_point_id = Column(Integer, ForeignKey('supply_points.id'))
    basic_charge_type_id = Column(Integer, ForeignKey('basic_charge_type.id'))
    plan_id = Column(Integer, ForeignKey('plan.id'))
    customer_number = Column(String(20), nullable=False)
    customer_name = Column(String(200), nullable=False)
    address = Column(String(200), nullable=False)
    invoice_number = Column(String(20), unique=True, nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    energy_charge_summer = Column(Integer, nullable=False)
    energy_charge_winter = Column(Integer, nullable=False)
    energy_charge_non_summer = Column(Integer, nullable=False)
    energy_charge_non_winter = Column(Integer, nullable=False)
    contracted_supply_capacity_negotiable = Column(Integer, nullable=False)
    power_factor_discount = Column(Integer, nullable=False)
    reverse_supply = Column(Integer, nullable=False)
    reverse_line = Column(Integer, nullable=False)
    total_price_with_tax = Column(Integer, nullable=False)
    tax = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))




class PeakDemand(db.Model):
    __tablename__ = 'peak_demand'
    id = Column(Integer, primary_key=True)
    monthly_usage_id = Column(Integer, ForeignKey('monthly_usage.id'))
    month_number = Column(Integer, nullable=False)
    peak_demand = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


############################################################################################################
# peak_demand_to_add = [
#     PeakDemand(monthly_usage_id=1, month_number=1, peak_demand=30),
#     PeakDemand(monthly_usage_id=2, month_number=2, peak_demand=50),
# ]
# session.add_all(region_to_add)
# # Commit the session to persist the changes to the database
# session.commit()
# # Close the session
# session.close()

############################################################################################################


class RenewableEnergyLevy(db.Model):
    __tablename__ = 'renewable_energy_levy'
    id = Column(Integer, primary_key=True)
    supply_point_id = Column(Integer, ForeignKey('supply_points.id'))
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class Month(db.Model):
    __tablename__ = 'month'
    id = Column(Integer, primary_key=True)
    supply_point_id = Column(Integer, ForeignKey('supply_points.id'))
    month_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))


class GovernmentSubsidy(db.Model):
    __tablename__ = 'government_subsidy'
    id = Column(Integer, primary_key=True)
    month_id = Column(Integer, ForeignKey('month.id'))
    price = Column(Float, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.now(UTC))
    updated_at = Column(DateTime, nullable=False, default=datetime.now(UTC), onupdate=datetime.now(UTC))



# # Create the tables
# with app.app_context():
#     db.create_all()

# if __name__ == '__main__':
#     app.run(debug=True)
