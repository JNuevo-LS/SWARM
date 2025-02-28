from dsgp4.tle import TLE, load_from_data
import numpy as np
import torch
import datetime
import copy

from dsgp4 import util
_, MU_EARTH, _, _, _, _, _, _=util.get_gravity_constants('wgs-84')
MU_EARTH = MU_EARTH*1e9

def compute_checksum(line): #also copied
    return sum((int(c) if c.isdigit() else c == '-') for c in line[0:68]) % 10

class CustomTLE(TLE):
    @staticmethod
    def custom_load_from_data(data, opsmode='i'): #copied and adapted from dsgp4 for compatibility
        xpdotp   =  1440.0 / (2.0 *np.pi)

        data['raan']=data['raan']%(2*np.pi)
        data['argument_of_perigee']=data['argument_of_perigee']%(2*np.pi)
        data['mean_anomaly']=data['mean_anomaly']%(2*np.pi)
    
        year = data['epoch_year'] + 2000

        epochdays = data['epoch_days']
        data['_epochdays'] = epochdays
        date_datetime = datetime.datetime(year-1, 12, 31, 0, 0, 0, 0)+datetime.timedelta(days = epochdays)
        date_string = date_datetime.strftime(format = '%Y-%m-%d %H:%M:%S.%f')
        data['epoch_year'] = date_datetime.year
        data['epoch_days'] = epochdays
        data['date_string'] = date_string
        #for SGP4:
        data['_bstar'] = torch.tensor(float(data["b_star"]))
        data['_ndot'] = torch.tensor(data['mean_motion_first_derivative']/(xpdotp*1440.0))
        data['_nddot']= torch.tensor(data['mean_motion_second_derivative']/(xpdotp*1440.0*1440))

        #for SGP4:
        data['_inclo'] = torch.tensor(np.deg2rad(data['inclination']))
        data['_nodeo'] = torch.tensor(np.deg2rad(data['raan']))
        data['_ecco'] = torch.tensor(data["eccentricity"])
        data['_argpo'] = torch.tensor(np.deg2rad(data['argument_of_perigee']))
        data['_mo'] = torch.tensor(np.deg2rad(data['mean_anomaly']))
        data['_no_kozai'] = torch.tensor(data['mean_motion'] / xpdotp)

        date_datetime = datetime.datetime(data['epoch_year']-1, 12, 31, 0, 0, 0, 0)+datetime.timedelta(days = data['epoch_days'])
        date_string = date_datetime.strftime(format = '%Y-%m-%d %H:%M:%S.%f')
        data['date_string'] = date_string
        data['date_mjd'] = util.from_datetime_to_mjd(util.from_string_to_datetime(date_string))
        data['semi_major_axis'] = (MU_EARTH/(data['mean_motion']**2))**(1.0/3.0)
        mon,day,hr,minute,sec = util.days2mdhms(year, epochdays);
        sec_whole, sec_fraction = divmod(sec, 1.0)
        data['_epochyr'] = torch.tensor(year)
        data['_jdsatepoch'] = torch.tensor(util.jday(year,mon,day,hr,minute,sec)[0]);
        data['_jdsatepochF'] = torch.tensor(util.jday(year,mon,day,hr,minute,sec)[1]);

        #I also add the semi-major axis:
        data['semi_major_axis'] = (MU_EARTH/(data['mean_motion']**2))**(1.0/3.0)
        try:
            data['_epoch'] = datetime.datetime(year, mon, day, hr, minute, int(sec_whole),
                                    int(sec_fraction * 1000000.0 // 1.0))
        except ValueError:
            # Sometimes a TLE says something like "2019 + 366.82137887 days"
            # which would be December 32nd which causes a ValueError.
            year, mon, day, hr, minute, sec = util.invjday(data['_jdsatepoch'])
            data['_epoch'] = datetime.datetime(year, mon, day, hr, minute, int(sec_whole),
                                    int(sec_fraction * 1000000.0 // 1.0))
        data['_opsmode']=opsmode
        return data

    def __init__(self, data):
        if isinstance(data, dict):
            self._data = self.custom_load_from_data(copy.deepcopy(data))
        else:
            # Fall back to the original behavior if data is not a dict.
            super().__init__(data)

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(f"{self.__class__.__name__} has no attribute {name}")

    def update(self, tle_data):
        """
        This function updates the TLE object with the given data.


        Parameters:
        ----------------
        tle_data (`dict`): dictionary of TLE data
        """
        d = copy.deepcopy(self._data)
        for k, v in tle_data.items():
            d[k] = v
        tle = CustomTLE(d)
        self._mo=tle['_mo']
        self._bstar=tle['_bstar']
        self._ndot=tle['_ndot']
        self._nddot=tle['_nddot']
        self._ecco= tle['_ecco']
        self._argpo=tle['_argpo']
        self._inclo=tle['_inclo']
        self._no_kozai=tle['_no_kozai']
        self._nodeo=tle['_nodeo']
        self._data = tle._data


    def __repr__(self):
        s = ""
        for key in self._data.keys():
            s += f"{key}: {self._data[key]}\n"
        return s
    
    def copy(self):
                # Create a deep copy of the internal data
        d = {k: (v.clone() if isinstance(v, torch.Tensor) else copy.deepcopy(v))
             for k, v in self._data.items()}
        # Return a new instance of CustomTLE instead of TLE
        return CustomTLE(d)