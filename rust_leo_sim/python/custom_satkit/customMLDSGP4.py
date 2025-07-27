import torch
import torch.nn as nn
from torch.nn.parameter import Parameter
from util import transform

class mldsgp4(nn.Module):
    def __init__(self, 
                normalization_R=6958.137, 
                normalization_V=7.947155867983262, 
                hidden_size=100, 
                input_correction=1e-2, 
                output_correction=0.8):
        """
        This class implements the ML-dSGP4 model, where dSGP4 inputs and outputs are corrected via neural networks, 
        better match simulated or observed higher-precision data.

        Parameters:
        ----------------
        normalization_R (``float``): normalization constant for x,y,z coordinates.
        normalization_V (``float``): normalization constant for vx,vy,vz coordinates.
        hidden_size (``int``): number of neurons in the hidden layers.
        input_correction (``float``): correction factor for the input layer.
        output_correction (``float``): correction factor for the output layer.
        """
        super().__init__()
        self.fc1=nn.Linear(6, hidden_size)
        self.fc2=nn.Linear(hidden_size,hidden_size)
        self.fc3=nn.Linear(hidden_size, 6)
        self.fc4=nn.Linear(6,hidden_size)
        self.fc5=nn.Linear(hidden_size, hidden_size)
        self.fc6=nn.Linear(hidden_size, 6)
        
        self.tanh = nn.Tanh()
        self.leaky_relu = nn.LeakyReLU(negative_slope=0.01)
        self.normalization_R=normalization_R
        self.normalization_V=normalization_V
        self.input_correction = Parameter(input_correction*torch.ones((6,)))
        self.output_correction = Parameter(output_correction*torch.ones((6,)))

    def forward(self, tles, tsinces):
        """
        This method computes the forward pass of the ML-dSGP4 model.
        It can take either a single or a list of `dsgp4.tle.TLE` objects, 
        and a torch.tensor of times since the TLE epoch in minutes.
        It then returns the propagated state in the TEME coordinate system. The output
        is normalized, to unnormalize and obtain km and km/s, you can use self.normalization_R constant for the position
        and self.normalization_V constant for the velocity.

        Parameters:
        ----------------
        tles (``dsgp4.tle.TLE`` or ``list``): a TLE object or a list of TLE objects.
        tsinces (``torch.tensor``): a torch.tensor of times since the TLE epoch in minutes.

        Returns:
        ----------------
        (``torch.tensor``): a tensor of len(tsince)x6 representing the corrected satellite position and velocity in normalized units (to unnormalize to km and km/s, use `self.normalization_R` for position, and `self.normalization_V` for velocity).
        """
        is_batch=hasattr(tles, '__len__')
        if is_batch:
            #this is the batch case, so we proceed and initialize the batch:
            _,tles=initialize_tle(tles,with_grad=True)
            x0 = torch.stack((tles._ecco, tles._argpo, tles._inclo, tles._mo, tles._no_kozai, tles._nodeo), dim=1)
        else:
            #this handles the case in which a singlee TLE is passed
            initialize_tle(tles,with_grad=True)
            x0 = torch.stack((tles._ecco, tles._argpo, tles._inclo, tles._mo, tles._no_kozai, tles._nodeo), dim=0).reshape(-1,6)
        x=self.leaky_relu(self.fc1(x0))
        x=self.leaky_relu(self.fc2(x))
        x=x0*(1+self.input_correction*self.tanh(self.fc3(x)))
        #now we need to substitute them back into the tles:
        tles._ecco=x[:,0]
        tles._argpo=x[:,1]
        tles._inclo=x[:,2]
        tles._mo=x[:,3]
        tles._no_kozai=x[:,4]
        tles._nodeo=x[:,5]
        if is_batch:    
            #we propagate the batch:
            states_teme=propagate_batch(tles,tsinces)
        else:
            states_teme=propagate(tles,tsinces)
        states_teme=states_teme.reshape(-1,6)
        #we now extract the output parameters to correct:
        x_out=torch.cat((states_teme[:,:3]/self.normalization_R, states_teme[:,3:]/self.normalization_V),dim=1)

        x=self.leaky_relu(self.fc4(x_out))
        x=self.leaky_relu(self.fc5(x))
        x=x_out*(1+self.output_correction*self.tanh(self.fc6(x)))
        return x

    def load_model(self, path, device='cpu'):
        """
        This method loads a model from a file.

        Parameters:
        ----------------
        path (``str``): path to the file where the model is stored.
        device (``str``): device where the model will be loaded. Default is 'cpu'.
        """
        self.load_state_dict(torch.load(path,map_location=torch.device(device)))
        self.eval()


def propagate_batch(tles, tsinces, initialized=True):
    """
    This function takes a list of TLEs and a tensor of times (which must be of same length), and returns the corresponding states.
    
    Parameters:
    ----------------
    tles (``list`` of ``dsgp4.tle.TLE``): list of TLE objects to be propagated
    tsinces (``torch.tensor``): propagation times in minutes (it has to be a tensor of the same size of the list of TLEs)
    initialized (``bool``): whether the TLEs have been initialized or not (default: True

    Returns:
    ----------------
    state (``torch.tensor``): (Nx2x3) tensor representing position and velocity in km and km/s, where the first dimension is the batch size.
    """
    from sgp4_batched import sgp4_batched
    if not initialized:
        _,tles=initialize_tle(tles)
    state=sgp4_batched(tles, tsinces)
    return state

def propagate(tle, tsinces, initialized=True):
    """
    This function takes a tensor of inputs and a TLE, and returns the corresponding state.
    In particular, multiple behaviors are supported:
    - if a single TLE is provided, then the function returns the state of the satellite at the requested time(s)
    - if a list of TLEs is provided, then the function returns the state of each satellite at the requested times

    In the second case, the length of the list of TLEs must be equal to the length of the tensor of times.
    
    Parameters:
    ----------------
    tle (``dsgp4.tle.TLE`` or ``list`` of ``dsgp4.tle.TLE``): TLE object or list of TLE objects to be propagated
    tsinces (``torch.tensor``): propagation times in minutes
    initialized (``bool``): whether the TLEs have been initialized or not (default: True)

    Returns:
    ----------------
    state (``torch.tensor``): (2x3) tensor representing position and velocity in km and km/s.
    """
    from sgp4 import sgp4
    if not initialized:
        initialize_tle(tle)
    state=sgp4(tle, tsinces)
    return state

def initialize_tle(tles,
                   gravity_constant_name="wgs-84",
                   with_grad=False):
    """
    This function takes a single `dsgp4.tle.TLE` object or a list of `dsgp4.tle.TLE` objects and initializes the SGP4 propagator.
    This is a necessary step to be ran before propagating TLEs (e.g. before calling `propagate` function).
    
    Parameters:
    ----------------
    tles (``dsgp4.tle.TLE`` or ``list`` of ``dsgp4.tle.TLE``): TLE object or list of TLE objects to be initialized
    gravity_constant_name (``str``): name of the gravity constant to be used (default: "wgs-84")    
    with_grad (``bool``): whether to use gradients or not (default: False)
    
    Returns:
    ----------------
    tle_elements (``torch.tensor``): tensor of TLE parameters (especially useful to retrieve gradients, when `with_grad` is `True`)
    """
    from dsgp4.sgp4init import sgp4init
    from dsgp4.sgp4init_batch import sgp4init_batch
    whichconst=transform.get_gravity_constants(gravity_constant_name)
    deep_space_counter=0

    if isinstance(tles,list):
        tle_elements=[]#torch.zeros((len(tles),9),requires_grad=with_grad)
        for tle in tles:
                x=torch.tensor([tle._bstar,
                            tle._ndot,
                            tle._nddot,
                            tle._ecco,
                            tle._argpo,
                            tle._inclo,
                            tle._mo,
                            tle._no_kozai,
                            tle._nodeo
                            ],requires_grad=with_grad)
                tle_elements.append(x)
        xx=torch.stack(tle_elements)
        try:
            tles_batch=tles[0].copy()
            sgp4init_batch(whichconst=whichconst,
                            opsmode='i',
                            satn=tle.satellite_catalog_number,
                            epoch=(tle._jdsatepoch+tle._jdsatepochF)-2433281.5,
                            xbstar=xx[:,0],
                            xndot=xx[:,1],
                            xnddot=xx[:,2],
                            xecco=xx[:,3],
                            xargpo=xx[:,4],
                            xinclo=xx[:,5],
                            xmo=xx[:,6],
                            xno_kozai=xx[:,7],
                            xnodeo=xx[:,8],
                            satellite_batch=tles_batch,
                            )
        except Exception as e:
            _error_string="Error: deep space propagation not supported (yet). The provided satellite has \
an orbital period above 225 minutes. If you want to let us know you need it or you want to \
contribute to implement it, open a PR or raise an issue at: https://github.com/esa/dSGP4."
            if str(e)==_error_string:
                deep_space_counter+=1
            else:
                raise e
        if deep_space_counter>0:
            print("Warning: "+str(deep_space_counter)+" TLEs were not initialized because they are in deep space. Deep space propagation is currently not supported.")
        return tle_elements, tles_batch

    else:
        tle_elements=torch.tensor([tles._bstar,
                                    tles._ndot,
                                    tles._nddot,
                                    tles._ecco,
                                    tles._argpo,
                                    tles._inclo,
                                    tles._mo,
                                    tles._no_kozai,
                                    tles._nodeo
                                    ],requires_grad=with_grad)
        sgp4init(whichconst=whichconst,
                            opsmode='i',
                            satn=tles.satellite_catalog_number,
                            epoch=(tles._jdsatepoch+tles._jdsatepochF)-2433281.5,
                            xbstar=tle_elements[0],
                            xndot=tle_elements[1],
                            xnddot=tle_elements[2],
                            xecco=tle_elements[3],
                            xargpo=tle_elements[4],
                            xinclo=tle_elements[5],
                            xmo=tle_elements[6],
                            xno_kozai=tle_elements[7],
                            xnodeo=tle_elements[8],
                            satellite=tles)
        return tle_elements

